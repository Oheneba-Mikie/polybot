import requests, time, datetime, sys, json

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"
TARGET_ASSET = "eth"
ORDER_SIZE = 5.0

print("=" * 65)
print("POLYBOT LIVE SPLIT-LEG ASYNCHRONOUS ARBITRAGE TESTER (LOCAL)")
print("Strategy: Buy Leg 1 when <= $0.45. Hunt for Leg 2 at <= (0.99 - Leg1).")
print("=" * 65)

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
session.mount("https://", adapter)

def get_active_market():
    now = int(time.time())
    cur_w = (now // 300) * 300
    for w_s in [cur_w, cur_w + 300]:
        slug = f"{TARGET_ASSET}-updown-5m-{w_s}"
        try:
            r = session.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
            if r and r[0].get("markets"):
                m = r[0]["markets"][0]
                tokens = json.loads(m.get("clobTokenIds", "[]"))
                if len(tokens) >= 2 and now < (w_s + 300):
                    return {
                        "slug": slug,
                        "title": r[0].get("title", slug),
                        "window_start": w_s,
                        "window_end": w_s + 300,
                        "up_token": tokens[0],
                        "down_token": tokens[1]
                    }
        except Exception:
            pass
    return None

def fetch_books(up_tok, dn_tok):
    try:
        r_up = session.get(f"{CLOB_HOST}/book?token_id={up_tok}", timeout=1.5).json()
        r_dn = session.get(f"{CLOB_HOST}/book?token_id={dn_tok}", timeout=1.5).json()
        
        asks_up = r_up.get("asks", [])
        asks_dn = r_dn.get("asks", [])
        
        best_up = min(asks_up, key=lambda x: float(x["price"])) if asks_up else None
        best_dn = min(asks_dn, key=lambda x: float(x["price"])) if asks_dn else None
        
        up_p = float(best_up["price"]) if best_up else 1.0
        up_s = float(best_up["size"]) if best_up else 0.0
        dn_p = float(best_dn["price"]) if best_dn else 1.0
        dn_s = float(best_dn["size"]) if best_dn else 0.0
        
        return up_p, up_s, dn_p, dn_s
    except Exception:
        return 1.0, 0.0, 1.0, 0.0

current_mkt = None
leg1_position = None
leg2_position = None
trade_history = []

while True:
    try:
        now = int(time.time())
        if not current_mkt or now >= current_mkt["window_end"]:
            # Evaluate last candle if holding naked leg
            if leg1_position and not leg2_position:
                print(f"⚠️ [CANDLE EXPIRED] Holding single leg {leg1_position['outcome']} @ ${leg1_position['price']:.2f}")
                trade_history.append({"status": "UNHEDGED_SINGLE", "leg1": leg1_position})
                
            current_mkt = get_active_market()
            leg1_position = None
            leg2_position = None
            if current_mkt:
                print(f"\n🟢 [NEW CANDLE] {current_mkt['slug']} (Active until {datetime.datetime.fromtimestamp(current_mkt['window_end'], tz=datetime.timezone.utc).strftime('%H:%M:%S UTC')})")
            else:
                time.sleep(2.0)
                continue
                
        t_rem = max(0, current_mkt["window_end"] - int(time.time()))
        up_p, up_s, dn_p, dn_s = fetch_books(current_mkt["up_token"], current_mkt["down_token"])
        comb = round(up_p + dn_p, 3)
        
        # State 1: Looking for Leg 1 (Any side <= $0.45 with >= 5 shares)
        if leg1_position is None and t_rem > 45:
            # Check if UP is cheap
            if up_p <= 0.45 and up_s >= 5.0:
                leg1_position = {
                    "outcome": "UP",
                    "price": up_p,
                    "shares": ORDER_SIZE,
                    "time": now,
                    "sec_in": 300 - t_rem,
                    "max_opp_price": round(0.99 - up_p, 3)
                }
                print(f"\n🎯 [LEG 1 FILLED] Bought 5.0 UP @ ${up_p:.2f} (Depth: {up_s:.0f}sh) | T-{t_rem}s")
                print(f"🏹 [HUNTING LEG 2] Need DOWN @ <= ${leg1_position['max_opp_price']:.2f} to guarantee profit!\n")
            # Check if DOWN is cheap
            elif dn_p <= 0.45 and dn_s >= 5.0:
                leg1_position = {
                    "outcome": "DOWN",
                    "price": dn_p,
                    "shares": ORDER_SIZE,
                    "time": now,
                    "sec_in": 300 - t_rem,
                    "max_opp_price": round(0.99 - dn_p, 3)
                }
                print(f"\n🎯 [LEG 1 FILLED] Bought 5.0 DOWN @ ${dn_p:.2f} (Depth: {dn_s:.0f}sh) | T-{t_rem}s")
                print(f"🏹 [HUNTING LEG 2] Need UP @ <= ${leg1_position['max_opp_price']:.2f} to guarantee profit!\n")
                
        # State 2: Holding Leg 1, hunting for Leg 2
        elif leg1_position is not None and leg2_position is None:
            needed_price = leg1_position["max_opp_price"]
            if leg1_position["outcome"] == "UP":
                # Need DOWN
                if dn_p <= needed_price and dn_s >= 5.0:
                    leg2_position = {
                        "outcome": "DOWN",
                        "price": dn_p,
                        "shares": ORDER_SIZE,
                        "delay": now - leg1_position["time"]
                    }
                    total_cost = round(leg1_position["price"] + dn_p, 3)
                    profit = round((1.0 - total_cost) * ORDER_SIZE, 3)
                    pct = round(((1.0 - total_cost) / total_cost) * 100, 1)
                    print(f"\n🎉 [LEG 2 FILLED] Bought 5.0 DOWN @ ${dn_p:.2f} after {leg2_position['delay']}s! | T-{t_rem}s")
                    print(f"🔒 [PAIR COMPLETE] Combined Cost: ${total_cost:.3f} | Locked Profit: +${profit:.3f} (+{pct}%)\n")
                    trade_history.append({"status": "PAIRED", "comb": total_cost, "profit": profit})
            else:
                # Need UP
                if up_p <= needed_price and up_s >= 5.0:
                    leg2_position = {
                        "outcome": "UP",
                        "price": up_p,
                        "shares": ORDER_SIZE,
                        "delay": now - leg1_position["time"]
                    }
                    total_cost = round(leg1_position["price"] + up_p, 3)
                    profit = round((1.0 - total_cost) * ORDER_SIZE, 3)
                    pct = round(((1.0 - total_cost) / total_cost) * 100, 1)
                    print(f"\n🎉 [LEG 2 FILLED] Bought 5.0 UP @ ${up_p:.2f} after {leg2_position['delay']}s! | T-{t_rem}s")
                    print(f"🔒 [PAIR COMPLETE] Combined Cost: ${total_cost:.3f} | Locked Profit: +${profit:.3f} (+{pct}%)\n")
                    trade_history.append({"status": "PAIRED", "comb": total_cost, "profit": profit})

        # Console ticker every 1.5s
        if not hasattr(fetch_books, "_last_t") or time.time() - fetch_books._last_t >= 1.5:
            fetch_books._last_t = time.time()
            if leg1_position and not leg2_position:
                target_str = f"🏹 HUNTING { 'DOWN' if leg1_position['outcome']=='UP' else 'UP' } <= ${leg1_position['max_opp_price']:.2f}"
            elif leg1_position and leg2_position:
                target_str = "🔒 PAIR LOCKED (100% Hedged)"
            else:
                target_str = "🔍 SCANNING FOR ENTRY (<= $0.45)"
            print(f"T-{t_rem:03d}s | UP: ${up_p:.2f} ({up_s:3.0f}sh) | DN: ${dn_p:.2f} ({dn_s:3.0f}sh) | Sum: ${comb:.3f} | {target_str}")
            
        time.sleep(0.15)
    except KeyboardInterrupt:
        break
    except Exception as e:
        time.sleep(0.5)
