import os
import sys
import time
import json
import ssl
import threading
import datetime
import requests
import websocket

# Configure UTF-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

DURATION_SECONDS = 300  # 5 minutes

def get_current_btc_market():
    now = time.time()
    w_s = int(now // 300) * 300
    slug = f"btc-updown-5m-{w_s}"
    try:
        r = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=10)
        events = r.json()
        if events and events[0].get("markets"):
            m = events[0]["markets"][0]
            clob_tokens = json.loads(m.get("clobTokenIds", "[]"))
            outcomes = [str(o).lower() for o in json.loads(m.get("outcomes", "[]"))]
            up_id = clob_tokens[0]
            down_id = clob_tokens[1]
            if len(outcomes) >= 2:
                if outcomes[0] in ("up", "yes"):
                    up_id, down_id = clob_tokens[0], clob_tokens[1]
                else:
                    down_id, up_id = clob_tokens[0], clob_tokens[1]
            return {
                "slug": slug,
                "title": m.get("question", slug),
                "up_id": up_id,
                "down_id": down_id,
                "w_s": w_s,
                "w_e": w_s + 300
            }
    except Exception as e:
        print(f"[ERROR] Gamma lookup error: {e}")
    return None

class HighPrecisionPairArbAuditor:
    def __init__(self, duration=300):
        self.duration = duration
        self.start_time = None
        self.end_time = None
        self.market = None
        self.up_id = None
        self.down_id = None
        
        self.books = {
            "up": {"asks": {}, "best_ask": None, "best_size": 0.0, "last_update_ms": 0},
            "down": {"asks": {}, "best_ask": None, "best_size": 0.0, "last_update_ms": 0}
        }
        self.lock = threading.Lock()
        
        # Tracking opportunities
        self.total_ticks = 0
        self.active_opportunity = None
        self.completed_opportunities = []
        self.all_snapshots = []
        self.running = True

    def start(self):
        print("="*100)
        print("🚀 STARTING 5-MINUTE HIGH-PRECISION MILLISECOND PAIR ARBITRAGE SCANNER")
        print(f"Monitoring: Polymarket CLOB WebSocket for Combined Asks < $1.00 (e.g. <= 0.98, <= 0.99)")
        print(f"Duration  : {self.duration} seconds")
        print("="*100 + "\n")

        self.market = get_current_btc_market()
        if not self.market:
            print("[ERROR] Could not find active 5m BTC market. Retrying in 2s...")
            time.sleep(2)
            self.market = get_current_btc_market()
            if not self.market:
                print("[FATAL] Exiting.")
                return

        self.up_id = self.market["up_id"]
        self.down_id = self.market["down_id"]
        print(f"🎯 Target Market : {self.market['title']}")
        print(f"   Slug          : {self.market['slug']}")
        print(f"   UP Token ID   : {self.up_id}")
        print(f"   DOWN Token ID : {self.down_id}\n")

        # Pre-populate orderbook via REST API
        self.initial_book_fetch()

        self.start_time = time.time()
        self.end_time = self.start_time + self.duration

        # Start WebSocket connection
        self.connect_ws()

    def initial_book_fetch(self):
        try:
            r_up = requests.get(f"{CLOB_HOST}/book?token_id={self.up_id}", timeout=5).json()
            r_dn = requests.get(f"{CLOB_HOST}/book?token_id={self.down_id}", timeout=5).json()
            
            with self.lock:
                up_asks = sorted(r_up.get("asks", []), key=lambda a: float(a["price"]))
                dn_asks = sorted(r_dn.get("asks", []), key=lambda a: float(a["price"]))
                
                if up_asks:
                    self.books["up"]["best_ask"] = float(up_asks[0]["price"])
                    self.books["up"]["best_size"] = float(up_asks[0].get("size", 0))
                if dn_asks:
                    self.books["down"]["best_ask"] = float(dn_asks[0]["price"])
                    self.books["down"]["best_size"] = float(dn_asks[0].get("size", 0))
            
            print(f"Initial REST Book: UP=${self.books['up']['best_ask']} ({self.books['up']['best_size']:.1f}sh) | DOWN=${self.books['down']['best_ask']} ({self.books['down']['best_size']:.1f}sh)\n")
        except Exception as e:
            print(f"Initial REST fetch error: {e}")

    def connect_ws(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        def on_open(ws):
            print("✅ WebSocket Connected! Subscribing to Order Book Level 2 feeds...")
            sub = {
                "type": "market",
                "assets_ids": [self.up_id, self.down_id],
                "custom_feature_enabled": True
            }
            ws.send(json.dumps(sub))

        def on_message(ws, message):
            if not self.running or time.time() > self.end_time:
                ws.close()
                return

            if message == "PONG":
                return

            recv_ts_ms = time.time() * 1000
            try:
                data = json.loads(message)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    self.process_ws_item(item, recv_ts_ms)
            except Exception as e:
                pass

        def on_close(ws, c, m):
            if self.running and time.time() < self.end_time:
                time.sleep(1)
                self.connect_ws()

        ws_app = websocket.WebSocketApp(
            WS_URL,
            header={"User-Agent": "Mozilla/5.0"},
            on_open=on_open,
            on_message=on_message,
            on_close=on_close
        )
        
        ws_thread = threading.Thread(
            target=lambda: ws_app.run_forever(sslopt={"context": ctx}, ping_interval=15, ping_timeout=10),
            daemon=True
        )
        ws_thread.start()

        # Monitoring loop
        last_heartbeat = time.time()
        while time.time() < self.end_time:
            time.sleep(0.5)
            # Market boundary check
            now = time.time()
            if now >= self.market["w_e"]:
                print("\n🔄 5-Minute Candle Boundary Reached. Refreshing market tokens...")
                new_m = get_current_btc_market()
                if new_m and new_m["slug"] != self.market["slug"]:
                    self.market = new_m
                    self.up_id = new_m["up_id"]
                    self.down_id = new_m["down_id"]
                    print(f"🎯 New Market: {new_m['slug']}\n")
                    self.initial_book_fetch()
                    # Re-subscribe WS
                    try:
                        sub = {
                            "type": "market",
                            "assets_ids": [self.up_id, self.down_id],
                            "custom_feature_enabled": True
                        }
                        ws_app.send(json.dumps(sub))
                    except Exception:
                        pass

            if now - last_heartbeat >= 15.0:
                last_heartbeat = now
                with self.lock:
                    u_p = self.books["up"]["best_ask"]
                    u_s = self.books["up"]["best_size"]
                    d_p = self.books["down"]["best_ask"]
                    d_s = self.books["down"]["best_size"]
                    rem = int(self.end_time - now)
                    if u_p and d_p:
                        comb = u_p + d_p
                        status = "🔥 ARB OPEN" if comb < 1.00 else "NORMAL"
                        print(f"[{datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S')}] {rem:>3}s left | UP: ${u_p:.3f} ({u_s:.1f}sh) + DN: ${d_p:.3f} ({d_s:.1f}sh) = ${comb:.4f} | {status} | Arbs Found: {len(self.completed_opportunities)}")

        self.running = False
        print("\n" + "="*100)
        print("🏁 5-MINUTE AUDIT COMPLETE. GENERATING STATISTICAL REPORT...")
        print("="*100)
        self.generate_report()

    def process_ws_item(self, item, recv_ts_ms):
        asset_id = str(item.get("asset_id") or "")
        side_key = "up" if asset_id == self.up_id else ("down" if asset_id == self.down_id else None)
        if not side_key:
            return

        ev_type = item.get("event_type") or item.get("type")
        updated = False

        with self.lock:
            self.total_ticks += 1
            if ev_type == "book" or "asks" in item:
                asks = item.get("asks", [])
                if asks:
                    s_asks = sorted(asks, key=lambda a: float(a["price"]))
                    self.books[side_key]["best_ask"] = float(s_asks[0]["price"])
                    self.books[side_key]["best_size"] = float(s_asks[0].get("size", 0))
                    self.books[side_key]["last_update_ms"] = recv_ts_ms
                    updated = True
            elif ev_type == "price_change":
                changes = item.get("price_changes", []) or [item]
                for ch in changes:
                    b_ask = ch.get("best_ask")
                    b_sz = ch.get("best_ask_size") or ch.get("size")
                    if b_ask is not None:
                        self.books[side_key]["best_ask"] = float(b_ask)
                        if b_sz is not None:
                            self.books[side_key]["best_size"] = float(b_sz)
                        self.books[side_key]["last_update_ms"] = recv_ts_ms
                        updated = True

            if not updated:
                return

            u_p = self.books["up"]["best_ask"]
            u_s = self.books["up"]["best_size"]
            d_p = self.books["down"]["best_ask"]
            d_s = self.books["down"]["best_size"]

            if u_p is None or d_p is None:
                return

            combined = u_p + d_p
            dt_str = datetime.datetime.fromtimestamp(recv_ts_ms / 1000.0, datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]

            is_arb = (combined < 1.000)

            if is_arb:
                max_pairs = min(u_s, d_s)
                profit_per_pair = 1.00 - combined
                total_risk_free_profit = max_pairs * profit_per_pair
                roi_pct = (profit_per_pair / combined) * 100.0

                if self.active_opportunity is None:
                    # New arb started
                    self.active_opportunity = {
                        "start_time_ms": recv_ts_ms,
                        "start_dt": dt_str,
                        "min_pair_cost": combined,
                        "initial_up_ask": u_p,
                        "initial_up_size": u_s,
                        "initial_down_ask": d_p,
                        "initial_down_size": d_s,
                        "max_available_shares": max_pairs,
                        "max_profit_usd": total_risk_free_profit,
                        "ticks": 1
                    }
                    print(f"\n⚡ [{dt_str}] >>> PAIR ARB DETECTED! <<<")
                    print(f"   UP Ask  : ${u_p:.4f} ({u_s:.2f} shares available)")
                    print(f"   DOWN Ask: ${d_p:.4f} ({d_s:.2f} shares available)")
                    print(f"   COMBINED: ${combined:.4f} (Under $1.00 by {profit_per_pair*100:.2f}¢)")
                    print(f"   INSTANT SWEEPABLE: {max_pairs:.2f} full pairs")
                    print(f"   MAX RISK-FREE PROFIT: +${total_risk_free_profit:.4f} USDC (+{roi_pct:.2f}% ROI)\n")
                else:
                    # Ongoing arb update
                    self.active_opportunity["ticks"] += 1
                    if combined < self.active_opportunity["min_pair_cost"]:
                        self.active_opportunity["min_pair_cost"] = combined
                    if max_pairs > self.active_opportunity["max_available_shares"]:
                        self.active_opportunity["max_available_shares"] = max_pairs
                    if total_risk_free_profit > self.active_opportunity["max_profit_usd"]:
                        self.active_opportunity["max_profit_usd"] = total_risk_free_profit
            else:
                if self.active_opportunity is not None:
                    # Arb just ended
                    duration_ms = recv_ts_ms - self.active_opportunity["start_time_ms"]
                    self.active_opportunity["end_time_ms"] = recv_ts_ms
                    self.active_opportunity["end_dt"] = dt_str
                    self.active_opportunity["duration_ms"] = round(duration_ms, 2)
                    
                    # Determine which leg caused it to close
                    close_reason = f"UP moved to ${u_p:.3f}" if side_key == "up" else f"DOWN moved to ${d_p:.3f}"
                    self.active_opportunity["closed_by"] = close_reason
                    
                    print(f"🛑 [{dt_str}] ARB CLOSED | Duration: {duration_ms:.1f} ms ({self.active_opportunity['ticks']} ticks) | Reason: {close_reason} -> Combined: ${combined:.4f}")
                    self.completed_opportunities.append(self.active_opportunity)
                    self.active_opportunity = None

    def generate_report(self):
        total_arbs = len(self.completed_opportunities)
        sub_98 = [o for o in self.completed_opportunities if o["min_pair_cost"] <= 0.98]
        sub_99 = [o for o in self.completed_opportunities if 0.98 < o["min_pair_cost"] <= 0.99]
        sub_100 = [o for o in self.completed_opportunities if 0.99 < o["min_pair_cost"] < 1.00]

        durations = [o["duration_ms"] for o in self.completed_opportunities]
        avg_duration = sum(durations)/len(durations) if durations else 0.0
        max_duration = max(durations) if durations else 0.0
        min_duration = min(durations) if durations else 0.0

        total_potential_profit = sum(o["max_profit_usd"] for o in self.completed_opportunities)
        total_potential_shares = sum(o["max_available_shares"] for o in self.completed_opportunities)

        summary_data = {
            "audit_start": datetime.datetime.fromtimestamp(self.start_time, datetime.timezone.utc).isoformat(),
            "audit_end": datetime.datetime.fromtimestamp(time.time(), datetime.timezone.utc).isoformat(),
            "total_ws_ticks_processed": self.total_ticks,
            "total_opportunities_found": total_arbs,
            "sub_0_98_count": len(sub_98),
            "sub_0_99_count": len(sub_99),
            "sub_1_00_count": len(sub_100),
            "duration_stats_ms": {
                "avg": round(avg_duration, 2),
                "min": round(min_duration, 2),
                "max": round(max_duration, 2)
            },
            "total_potential_profit_usdc": round(total_potential_profit, 4),
            "total_available_pairs": round(total_potential_shares, 2),
            "opportunities": self.completed_opportunities
        }

        with open("scratch/live_5m_pair_arb_audit.json", "w") as fp:
            json.dump(summary_data, fp, indent=2)

        print("\n" + "="*100)
        print("📊 5-MINUTE LIVE PAIR ARBITRAGE AUDIT SUMMARY")
        print("="*100)
        print(f"Total WebSocket Ticks Processed : {self.total_ticks:,}")
        print(f"Total Pair Arb Windows Found   : {total_arbs}")
        print(f"  • Super-Deep (<= $0.98)       : {len(sub_98)}")
        print(f"  • Prime      ($0.98 - $0.99)  : {len(sub_99)}")
        print(f"  • Micro-Edge ($0.99 - $1.00)  : {len(sub_100)}")
        print(f"Window Lifespan (Duration)      : Avg: {avg_duration:.1f}ms | Min: {min_duration:.1f}ms | Max: {max_duration:.1f}ms")
        print(f"Total Sweepable Shares          : {total_potential_shares:.2f} pairs")
        print(f"Total Theoretical Risk-Free $   : +${total_potential_profit:.4f} USDC")
        print("="*100)

if __name__ == "__main__":
    auditor = HighPrecisionPairArbAuditor(duration=300)
    auditor.start()
