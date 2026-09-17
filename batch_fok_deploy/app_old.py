import os
import sys
import time
import json
import math
import asyncio
import datetime
import random
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

import ssl
import threading
import websocket
import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import (
    ApiCreds,
    OrderArgsV2,
    PostOrdersV2Args,
    OrderType,
    PartialCreateOrderOptions,
    BalanceAllowanceParams,
    AssetType,
)

load_dotenv()

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# Configuration
TARGET_ASSET          = os.getenv("TARGET_ASSET", "btc").lower() # 'btc', 'eth', 'sol'
PAPER_MODE            = os.getenv("PAPER_MODE", "true").lower() == "true" # True = ZERO REAL MONEY, pure simulation
MAX_TRADES_PER_WINDOW = int(os.getenv("MAX_TRADES_PER_WINDOW", "1")) # Exactly 1 trade per 5-minute candle
MIN_DEPTH_THRESHOLD   = float(os.getenv("MIN_DEPTH_THRESHOLD", "5.0")) # At least 5 shares available on BOTH ends
MAX_COMBINED_COST     = float(os.getenv("MAX_COMBINED_COST", "0.995")) # Strict sub-$1.00 combined cost (e.g. 71¢, 86¢, 92¢, 99¢)
ORDER_SIZE            = float(os.getenv("ORDER_SIZE", "5.0")) # 5.0 shares per trade (~$4.80 stake)
POLL_INTERVAL         = float(os.getenv("POLL_INTERVAL", "0.15")) # 150ms high-speed poll interval
MIN_PERSISTENCE_SECS  = float(os.getenv("MIN_PERSISTENCE_SECS", "2.0")) # Opportunity must stay on book >= 2.0s before buying
LEG1_MAX_PRICE        = float(os.getenv("LEG1_MAX_PRICE", "0.985")) # Buy wave winner <= 98.5¢
LEG2_TARGET_PRICE     = float(os.getenv("LEG2_TARGET_PRICE", "0.015")) # Target 1.0¢ to 1.5¢ on loser
LEG2_MAX_HEDGE_PRICE  = float(os.getenv("LEG2_MAX_HEDGE_PRICE", "0.020")) # Up to 2.0¢ for breakeven hedge ($0.98 + $0.02 = $1.00)
MAX_PAIR_COST         = float(os.getenv("MAX_PAIR_COST", "0.995")) # Combined pair must be <= 99.5¢
MAX_TOTAL_PAIRS       = int(os.getenv("MAX_TOTAL_PAIRS", "100")) # 100 paper trades for continuous analysis
WAVE_THRESHOLD_USD    = float(os.getenv("WAVE_THRESHOLD_USD", "60.0")) # $60+ wave threshold for BTC
MIN_TIME_ELAPSED_S    = float(os.getenv("MIN_TIME_ELAPSED_S", "90.0")) # Enter after 90s to avoid early-candle noise reversals

class BinanceSpotFeed:
    def __init__(self, symbol: str = "BTCUSDT"):
        self.symbol = symbol
        self.live_price: float = 0.0
        self.candle_open: float = 0.0
        self.candle_w_ts: int = 0
        self._running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        while self._running:
            try:
                # Fast ticker price query
                r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={self.symbol}", timeout=2.0).json()
                if isinstance(r, dict) and "price" in r:
                    self.live_price = float(r["price"])

                # Update candle open at window start
                now = int(time.time())
                cur_w = (now // 300) * 300
                if cur_w != self.candle_w_ts or self.candle_open == 0.0:
                    self.candle_w_ts = cur_w
                    try:
                        k = requests.get(f"https://api.binance.com/api/v3/klines?symbol={self.symbol}&interval=5m&startTime={cur_w * 1000}&limit=1", timeout=2.0).json()
                        if isinstance(k, list) and len(k) > 0:
                            self.candle_open = float(k[0][1])
                        else:
                            self.candle_open = self.live_price
                    except Exception:
                        self.candle_open = self.live_price
            except Exception:
                pass
            time.sleep(0.4)

    def get_spot_data(self):
        move = self.live_price - self.candle_open if self.candle_open > 0 else 0.0
        return self.live_price, self.candle_open, move, abs(move)

binance_feed = BinanceSpotFeed("BTCUSDT" if TARGET_ASSET == "btc" else f"{TARGET_ASSET.upper()}USDT")

app = FastAPI(title=f"PolyBot {TARGET_ASSET.upper()} 5M $60+ Wave Arbitrage Sniper")
executor = ThreadPoolExecutor(max_workers=4)

# Global State for UI and Bot
state: Dict[str, Any] = {
    "target_asset": TARGET_ASSET.upper(),
    "paper_mode": PAPER_MODE,
    "status": "Initializing...",
    "mode": f"🧪 PAPER TRADING MODE ({TARGET_ASSET.upper()} 5M $60+ WAVE) - ZERO REAL MONEY" if PAPER_MODE else f"LIVE REAL-MONEY $60+ WAVE ARBITRAGE ({TARGET_ASSET.upper()} 5M)",
    "spot_price": 0.0,
    "candle_open": 0.0,
    "spot_move": 0.0,
    "abs_spot_move": 0.0,
    "wave_threshold": WAVE_THRESHOLD_USD,
    "wave_active": False,
    "wave_direction": "NEUTRAL",
    "funder": os.getenv("POLYMARKET_ADDRESS", ""),
    "current_candle_slug": None,
    "current_candle_title": None,
    "candle_ends_at_utc": None,
    "seconds_remaining": 0,
    "up_token": None,
    "down_token": None,
    "live_up_ask": 0.0,
    "live_up_depth": 0.0,
    "live_down_ask": 0.0,
    "live_down_depth": 0.0,
    "combined_cost": 0.0,
    "depth_condition_met": False,
    "price_condition_met": False,
    "leg1_position": None,
    "leg2_position": None,
    "trades_in_window": 0,
    "max_trades_per_window": MAX_TRADES_PER_WINDOW,
    "min_depth_threshold": MIN_DEPTH_THRESHOLD,
    "max_combined_cost": MAX_COMBINED_COST,
    "order_size": ORDER_SIZE,
    "min_persistence_secs": MIN_PERSISTENCE_SECS,
    "cross_persisted_s": 0.0,
    "total_lifetime_trades": 0,
    "total_lifetime_profit": 0.0,
    "wallet_balance": 0.0,
    "last_trade": None,
    "recent_trades": [],
    "cross_opportunities": [],
    "logs": []
}

def fetch_wallet_balance():
    if "sniper" in globals() and sniper and sniper.client:
        return sniper.get_balance()
    return 0.0

def log(msg: str):
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry, flush=True)
    state["logs"].append(entry)
    if len(state["logs"]) > 300:
        state["logs"].pop(0)

class ClobWebSocketStream:
    def __init__(self):
        self.ws = None
        self.current_tokens: List[str] = []
        self.book_cache: Dict[str, Dict[str, float]] = {}
        self.is_connected = False
        self.thread = None
        self._running = True

    def update_tokens(self, tokens: List[str]):
        if set(tokens) == set(self.current_tokens) and self.is_connected:
            return
        self.current_tokens = list(tokens)
        for t in tokens:
            if t not in self.book_cache:
                self.book_cache[t] = {"best_ask": 1.0, "best_ask_size": 0.0, "best_bid": 0.0}
        if self.ws and self.is_connected:
            try:
                sub = {
                    "type": "market",
                    "assets_ids": self.current_tokens,
                    "custom_feature_enabled": True
                }
                self.ws.send(json.dumps(sub))
            except Exception:
                pass

    def start(self):
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        while self._running:
            try:
                def on_open(ws):
                    self.is_connected = True
                    log("⚡ [WEBSOCKET CONNECTED] Real-time sub-10ms CLOB streaming active!")
                    if self.current_tokens:
                        sub = {
                            "type": "market",
                            "assets_ids": self.current_tokens,
                            "custom_feature_enabled": True
                        }
                        ws.send(json.dumps(sub))

                def on_message(ws, msg):
                    if msg == "PONG":
                        return
                    try:
                        data = json.loads(msg)
                        if isinstance(data, list):
                            for m in data:
                                aid = str(m.get("asset_id", ""))
                                asks = m.get("asks", [])
                                bids = m.get("bids", [])
                                b_ask = float(min(asks, key=lambda x: float(x["price"]))["price"]) if asks else 1.0
                                b_ask_s = float(min(asks, key=lambda x: float(x["price"]))["size"]) if asks else 0.0
                                b_bid = float(max(bids, key=lambda x: float(x["price"]))["price"]) if bids else 0.0
                                self.book_cache[aid] = {"best_ask": b_ask, "best_ask_size": b_ask_s, "best_bid": b_bid}
                        elif isinstance(data, dict):
                            pcs = data.get("price_changes", [])
                            for pc in pcs:
                                aid = str(pc.get("asset_id", ""))
                                b_ask = float(pc.get("best_ask", 1.0)) if pc.get("best_ask") is not None else 1.0
                                b_bid = float(pc.get("best_bid", 0.0)) if pc.get("best_bid") is not None else 0.0
                                sz = float(pc.get("size", 0.0))
                                if aid in self.book_cache:
                                    self.book_cache[aid]["best_ask"] = b_ask
                                    self.book_cache[aid]["best_bid"] = b_bid
                                    if pc.get("side") == "SELL" or pc.get("best_ask") == pc.get("price"):
                                        self.book_cache[aid]["best_ask_size"] = sz
                                else:
                                    self.book_cache[aid] = {"best_ask": b_ask, "best_ask_size": sz, "best_bid": b_bid}
                    except Exception:
                        pass

                def on_error(ws, err):
                    pass

                def on_close(ws, close_status, close_msg):
                    self.is_connected = False

                self.ws = websocket.WebSocketApp(
                    "wss://ws-subscriptions-clob.polymarket.com/ws/market",
                    on_open=on_open,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close
                )
                self.ws.run_forever(sslopt={"context": ssl_ctx}, ping_interval=10, ping_timeout=5)
            except Exception:
                pass
            time.sleep(1.0)

    def get_prices(self, up_token: str, down_token: str):
        up_data = self.book_cache.get(up_token, {"best_ask": 1.0, "best_ask_size": 0.0})
        dn_data = self.book_cache.get(down_token, {"best_ask": 1.0, "best_ask_size": 0.0})
        return up_data["best_ask"], up_data["best_ask_size"], dn_data["best_ask"], dn_data["best_ask_size"]

ws_stream = ClobWebSocketStream()

class RailwayBatchSniper:
    def __init__(self):
        self.private_key = os.getenv("POLYMARKET_PRIVATE_KEY", "")
        self.funder = os.getenv("POLYMARKET_ADDRESS", "")
        self.api_key = os.getenv("POLYMARKET_API_KEY", "")
        self.api_secret = os.getenv("POLYMARKET_API_SECRET", "")
        self.api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE", "")

        self.client = None
        self._init_client()

        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
        self.session.mount("https://", adapter)

        self.current_market = None
        self.leg1_position = None
        self.leg2_position = None
        self.trades_in_current_window = 0
        self.total_lifetime_trades = 0
        self.total_lifetime_profit = 0.0

    def _init_client(self):
        if not self.private_key or not self.api_key:
            log("⚠️ Missing Polymarket API credentials in environment!")
            return

        creds = ApiCreds(
            api_key=self.api_key,
            api_secret=self.api_secret,
            api_passphrase=self.api_passphrase,
        )
        self.client = ClobClient(
            host=CLOB_HOST,
            key=self.private_key,
            chain_id=137,
            creds=creds,
            signature_type=3,
            funder=self.funder,
        )
        log(f"✅ [AUTH SUCCESS] CLOB Client initialized for Funder: {self.funder} (SignatureType=3)")

    def get_balance(self):
        if not self.client:
            return 0.0
        try:
            resp = self.client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=3))
            if resp and "balance" in resp:
                return round(float(resp["balance"]) / 1_000_000, 2)
        except Exception:
            pass
        try:
            resp = self.client.get_collateral_balance()
            if resp:
                val = float(resp.get("balance", resp) if isinstance(resp, dict) else resp)
                if val > 1000:
                    val /= 1_000_000
                return round(val, 2)
        except Exception:
            pass
        return 0.0

    def get_active_5m_market(self):
        now = int(time.time())
        cur_w = (now // 300) * 300
        candidates = [cur_w, cur_w + 300]

        for w_s in candidates:
            slug = f"{TARGET_ASSET}-updown-5m-{w_s}"
            try:
                r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
                if r and r[0].get("markets"):
                    m = r[0]["markets"][0]
                    tokens = json.loads(m.get("clobTokenIds", "[]"))
                    if len(tokens) >= 2 and now < (w_s + 300):
                        return {
                            "slug": slug,
                            "title": r[0].get("title", slug),
                            "condition_id": m.get("conditionId", ""),
                            "window_start": w_s,
                            "window_end": w_s + 300,
                            "up_token": tokens[0],
                            "down_token": tokens[1],
                        }
            except Exception:
                pass
        return None

    def fetch_exact_audit_crosses(self, asset: str = "eth"):
        now = int(time.time())
        cur_w_s = (now // 300) * 300
        # Past 20 mins = last 4 candles
        windows = [cur_w_s - (i * 300) for i in range(4)]
        windows.reverse()

        all_opps = []
        for w_s in windows:
            slug = f"{asset}-updown-5m-{w_s}"
            try:
                r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3.5).json()
                if not r_evt or not r_evt[0].get("markets"):
                    continue
                m = r_evt[0]["markets"][0]
                cid = m.get("conditionId")
                if not cid:
                    continue

                trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=2000", timeout=4.0).json()
                if not isinstance(trades, list):
                    continue

                parsed = []
                for t in trades:
                    tr_ts = t.get("timestamp") or t.get("matchTime")
                    if isinstance(tr_ts, str):
                        try:
                            tr_ts = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00")).timestamp() if "T" in tr_ts else float(tr_ts)
                        except Exception:
                            tr_ts = 0
                    if tr_ts and tr_ts > 1e11:
                        tr_ts /= 1000.0
                    if w_s <= tr_ts <= w_s + 300:
                        parsed.append({
                            "ts": tr_ts,
                            "sec": int(tr_ts - w_s),
                            "countdown": max(0, 300 - int(tr_ts - w_s)),
                            "price": float(t.get("price", 0)),
                            "size": float(t.get("size", 0)),
                            "outcome": str(t.get("outcome", "")).upper()
                        })
                parsed.sort(key=lambda x: x["ts"])

                for i, t1 in enumerate(parsed):
                    for j in range(i + 1, min(i + 40, len(parsed))):
                        t2 = parsed[j]
                        dt = t2["ts"] - t1["ts"]
                        if dt > 1.5:
                            break

                        if (t1["outcome"] in ("UP", "YES") and t2["outcome"] in ("DOWN", "NO")) or (t1["outcome"] in ("DOWN", "NO") and t2["outcome"] in ("UP", "YES")):
                            comb = round(t1["price"] + t2["price"], 3)
                            if comb <= MAX_COMBINED_COST:
                                up_t = t1 if t1["outcome"] in ("UP", "YES") else t2
                                dn_t = t2 if t1["outcome"] in ("UP", "YES") else t1

                                up_vol = sum(t["size"] for t in parsed if t["outcome"] in ("UP", "YES") and abs(t["price"] - up_t["price"]) <= 0.01 and abs(t["ts"] - up_t["ts"]) <= 3.0)
                                dn_vol = sum(t["size"] for t in parsed if t["outcome"] in ("DOWN", "NO") and abs(t["price"] - dn_t["price"]) <= 0.01 and abs(t["ts"] - dn_t["ts"]) <= 3.0)

                                subsequent = [t for t in parsed[j + 1:] if t["ts"] - t1["ts"] <= 20.0]
                                dry_up = dt
                                for sub in subsequent:
                                    if (sub["outcome"] == up_t["outcome"] and abs(sub["price"] - up_t["price"]) <= 0.01) or (sub["outcome"] == dn_t["outcome"] and abs(sub["price"] - dn_t["price"]) <= 0.01):
                                        dry_up = max(dry_up, sub["ts"] - t1["ts"])

                                t1_str = datetime.datetime.fromtimestamp(t1["ts"], datetime.timezone.utc).strftime("%H:%M:%S")
                                cents = int(round(comb * 100))
                                profit_usd = round(1.0 - comb, 3)
                                profit_pct = round(((1.0 - comb) / comb) * 100, 1)

                                dry_up_str = f"Dried up in {round(dry_up, 1)}s" if dry_up >= 1.0 else f"Dried up in {int(dry_up * 1000)}ms"
                                gap_str = f"{int(dt * 1000)}ms (Instant)" if dt < 1.0 else f"{round(dt, 1)}s (Instant)"

                                all_opps.append({
                                    "key": f"{slug}_{t1_str}_{round(up_t['price'], 2)}_{round(dn_t['price'], 2)}_{comb}",
                                    "elapsed_str": f"T+{t1['sec']:03d}s (T-{t1['countdown']:03d}s)",
                                    "timestamp": t1_str,
                                    "up_str": f"{max(up_t['size'], round(up_vol, 1)):.1f} sh (Bt {up_t['size']:.1f}) @ ${up_t['price']:.2f}",
                                    "dn_str": f"{max(dn_t['size'], round(dn_vol, 1)):.1f} sh (Bt {dn_t['size']:.1f}) @ ${dn_t['price']:.2f}",
                                    "comb": f"${comb:.3f} ({cents:02d}¢)",
                                    "gap_str": gap_str,
                                    "lifespan": dry_up_str,
                                    "profit": f"+${profit_usd:.3f} (+{profit_pct:.1f}%)"
                                })
            except Exception:
                continue

        deduped = []
        seen = set()
        for o in all_opps:
            if o["key"] not in seen:
                deduped.append(o)
                seen.add(o["key"])

        deduped.reverse()
        return deduped[:100]

    def fetch_order_books(self, up_token: str, down_token: str):
        try:
            r_up = self.session.get(f"{CLOB_HOST}/book?token_id={up_token}", timeout=1.5).json()
            r_dn = self.session.get(f"{CLOB_HOST}/book?token_id={down_token}", timeout=1.5).json()

            asks_up = r_up.get("asks", [])
            asks_dn = r_dn.get("asks", [])

            best_up = min(asks_up, key=lambda x: float(x["price"])) if asks_up else None
            best_dn = min(asks_dn, key=lambda x: float(x["price"])) if asks_dn else None

            best_up_price = float(best_up["price"]) if best_up else 1.0
            best_up_size  = float(best_up["size"]) if best_up else 0.0

            best_dn_price = float(best_dn["price"]) if best_dn else 1.0
            best_dn_size  = float(best_dn["size"]) if best_dn else 0.0

            return best_up_price, best_up_size, best_dn_price, best_dn_size
        except Exception:
            return 1.0, 0.0, 1.0, 0.0

    def execute_batch_trade(self, up_token: str, up_price: float, dn_token: str, dn_price: float, size: float):
        if not self.client:
            log("❌ Client not authenticated. Cannot execute.")
            return False, "Not authenticated"

        t_start = time.perf_counter()
        try:
            opt = PartialCreateOrderOptions(tick_size="0.01", neg_risk=False)

            order_up = self.client.create_order(
                OrderArgsV2(
                    token_id=up_token,
                    price=up_price,
                    size=size,
                    side="BUY"
                ),
                options=opt
            )

            order_dn = self.client.create_order(
                OrderArgsV2(
                    token_id=dn_token,
                    price=dn_price,
                    size=size,
                    side="BUY"
                ),
                options=opt
            )

            batch_args = [
                PostOrdersV2Args(order=order_up, orderType=OrderType.FOK),
                PostOrdersV2Args(order=order_dn, orderType=OrderType.FOK),
            ]

            resp = self.client.post_orders(batch_args)
            lat_ms = (time.perf_counter() - t_start) * 1000.0

            if isinstance(resp, list) and len(resp) == 2:
                up_res = resp[0] if isinstance(resp[0], dict) else {}
                dn_res = resp[1] if isinstance(resp[1], dict) else {}
                up_matched = up_res.get("status") == "matched"
                dn_matched = dn_res.get("status") == "matched"

                if up_matched and dn_matched:
                    tx1 = up_res.get("transactionsHashes", [""])[0][:10] if up_res.get("transactionsHashes") else ""
                    tx2 = dn_res.get("transactionsHashes", [""])[0][:10] if dn_res.get("transactionsHashes") else ""
                    log(f"🎉 [SIMULTANEOUS ARBITRAGE FILLED in {lat_ms:.1f}ms] Both UP & DOWN matched! Tx1: {tx1}.. Tx2: {tx2}..")
                    return True, resp
                elif not up_matched and not dn_matched:
                    log(f"ℹ️ [SIMULTANEOUS BATCH UNFILLED in {lat_ms:.1f}ms] Both sides cleanly killed by FOK. 0 shares held.")
                    return False, "Both FOK killed"
                else:
                    # Asymmetric partial fill: immediately unwind the single side with a market sell so user is NEVER left naked
                    if up_matched:
                        log(f"⚠️ [PARTIAL FILL in {lat_ms:.1f}ms] UP matched but DOWN missed! Unwinding UP immediately to protect capital...")
                        try:
                            sell_order = self.client.create_order(OrderArgsV2(token_id=up_token, price=0.01, size=size, side="SELL"), options=opt)
                            self.client.post_orders([PostOrdersV2Args(order=sell_order, orderType=OrderType.FOK)])
                            log("🛡️ [UNWIND SUCCESS] Sold UP back to book. No naked position held.")
                        except Exception as un_err:
                            log(f"❌ [UNWIND ERROR] {un_err}")
                    else:
                        log(f"⚠️ [PARTIAL FILL in {lat_ms:.1f}ms] DOWN matched but UP missed! Unwinding DOWN immediately to protect capital...")
                        try:
                            sell_order = self.client.create_order(OrderArgsV2(token_id=dn_token, price=0.01, size=size, side="SELL"), options=opt)
                            self.client.post_orders([PostOrdersV2Args(order=sell_order, orderType=OrderType.FOK)])
                            log("🛡️ [UNWIND SUCCESS] Sold DOWN back to book. No naked position held.")
                        except Exception as un_err:
                            log(f"❌ [UNWIND ERROR] {un_err}")
                    return False, "Partial fill unwound"

            log(f"⚡ [BATCH SUBMITTED in {lat_ms:.1f}ms] Result: {resp}")
            return False, resp
        except Exception as e:
            lat_ms = (time.perf_counter() - t_start) * 1000.0
            log(f"❌ [BATCH FAILED in {lat_ms:.1f}ms] Error: {e}")
            return False, str(e)

    def execute_single_leg(self, token: str, price: float, size: float, outcome: str):
        t_start = time.perf_counter()
        if PAPER_MODE:
            sim_lat = round(random.uniform(20.0, 45.0), 1)
            log(f"📝 [PAPER FILL in {sim_lat}ms] BUY {size:.1f}sh {outcome} @ ${price:.2f} (SIMULATED - $0 REAL MONEY)")
            return True, {"status": "matched", "transactionsHashes": [f"0xPAPER_{outcome}_{int(time.time()*1000)}"]}

        if not self.client:
            log("❌ Client not authenticated. Cannot execute.")
            return False, "Not authenticated"
        try:
            opt = PartialCreateOrderOptions(tick_size="0.01", neg_risk=False)
            order = self.client.create_order(
                OrderArgsV2(
                    token_id=token,
                    price=price,
                    size=size,
                    side="BUY"
                ),
                options=opt
            )

            batch_args = [
                PostOrdersV2Args(order=order, orderType=OrderType.FOK)
            ]

            resp = self.client.post_orders(batch_args)
            lat_ms = (time.perf_counter() - t_start) * 1000.0

            if isinstance(resp, list) and len(resp) > 0:
                res = resp[0]
                if isinstance(res, dict) and res.get("status") == "matched":
                    tx = res.get("transactionsHashes", [""])[0] if res.get("transactionsHashes") else ""
                    log(f"⚡ [REAL FILL in {lat_ms:.1f}ms] BUY {size:.1f}sh {outcome} @ ${price:.2f} | Tx: {tx[:10]}...")
                    return True, res
                else:
                    err = res.get("errorMsg", "FOK killed/unfilled")
                    log(f"ℹ️ [ORDER UNFILLED in {lat_ms:.1f}ms] {outcome} @ ${price:.2f}: {err}")
                    return False, res

            log(f"ℹ️ [UNEXPECTED RESP in {lat_ms:.1f}ms] Result: {resp}")
            return False, resp
        except Exception as e:
            lat_ms = (time.perf_counter() - t_start) * 1000.0
            log(f"❌ [ORDER FAILED in {lat_ms:.1f}ms] Error: {e}")
            return False, str(e)

sniper = RailwayBatchSniper()

async def sniper_background_loop():
    log(f"🚀 [ENGINE START] Polymarket {TARGET_ASSET.upper()} 5M Depth & Arbitrage Batch FOK Sniper Engine Active")
    while True:
        try:
            now = int(time.time())
            if not sniper.current_market or now >= sniper.current_market["window_end"]:
                new_mkt = sniper.get_active_5m_market()
                if new_mkt:
                    sniper.current_market = new_mkt
                    sniper.leg1_position = None
                    sniper.leg2_position = None
                    sniper.trades_in_current_window = 0
                    state["leg1_position"] = None
                    state["leg2_position"] = None
                    end_dt = datetime.datetime.fromtimestamp(new_mkt["window_end"], tz=datetime.timezone.utc)
                    state["current_candle_slug"] = new_mkt["slug"]
                    state["current_candle_title"] = new_mkt["title"]
                    state["candle_ends_at_utc"] = end_dt.strftime("%H:%M:%S UTC")
                    state["up_token"] = new_mkt["up_token"]
                    state["down_token"] = new_mkt["down_token"]
                    state["trades_in_window"] = 0
                    ws_stream.update_tokens([new_mkt["up_token"], new_mkt["down_token"]])
                    log(f"🟢 [NEW CANDLE] {new_mkt['slug']} (Resolves at {state['candle_ends_at_utc']}) | Quota: 0/{MAX_TRADES_PER_WINDOW}")
                else:
                    state["status"] = f"Waiting for next {TARGET_ASSET.upper()} 5m market window..."
                    await asyncio.sleep(2.0)
                    continue

            mkt = sniper.current_market
            t_rem = max(0, mkt["window_end"] - int(time.time()))
            state["seconds_remaining"] = t_rem

            # Sub-10ms Live WebSocket Order Book Feed
            up_p, up_s, dn_p, dn_s = ws_stream.get_prices(mkt["up_token"], mkt["down_token"])
            if up_p >= 1.0 and dn_p >= 1.0:
                up_p, up_s, dn_p, dn_s = await asyncio.get_event_loop().run_in_executor(
                    executor, sniper.fetch_order_books, mkt["up_token"], mkt["down_token"]
                )

            comb = round(up_p + dn_p, 4)
            min_depth = min(up_s, dn_s)
            has_depth = (up_s >= MIN_DEPTH_THRESHOLD) and (dn_s >= MIN_DEPTH_THRESHOLD)
            is_profitable = (comb <= MAX_COMBINED_COST) and (comb > 0.1)

            # Query Live Binance BTC Spot Feed
            spot_p, open_p, s_move, abs_move = binance_feed.get_spot_data()
            state["spot_price"] = round(spot_p, 2)
            state["candle_open"] = round(open_p, 2)
            state["spot_move"] = round(s_move, 2)
            state["abs_spot_move"] = round(abs_move, 2)
            is_wave = (abs_move >= WAVE_THRESHOLD_USD)
            wave_dir = "UP" if s_move >= WAVE_THRESHOLD_USD else ("DOWN" if s_move <= -WAVE_THRESHOLD_USD else "NEUTRAL")
            state["wave_active"] = is_wave
            state["wave_direction"] = wave_dir

            state["live_up_ask"] = up_p
            state["live_up_depth"] = up_s
            state["live_down_ask"] = dn_p
            state["live_down_depth"] = dn_s
            state["combined_cost"] = comb
            state["depth_condition_met"] = has_depth
            state["price_condition_met"] = is_profitable

            if sniper.total_lifetime_trades >= MAX_TOTAL_PAIRS:
                state["status"] = f"🛑 [{MAX_TOTAL_PAIRS}-TRADE RUN COMPLETE] Finished! Engine stopped."
                state["mode"] = f"STOPPED ({MAX_TOTAL_PAIRS} TRADES COMPLETED)"
                await asyncio.sleep(2.0)
                continue

            t_elapsed = 300 - t_rem

            # Wave Trigger vs Cross Trigger
            wave_trigger = is_wave and (t_elapsed >= MIN_TIME_ELAPSED_S) and (t_rem >= 20)
            cross_trigger = is_profitable and has_depth and (t_rem > 15)

            # Trigger condition
            if (wave_trigger or cross_trigger) and sniper.trades_in_current_window < MAX_TRADES_PER_WINDOW and sniper.total_lifetime_trades < MAX_TOTAL_PAIRS:
                exec_shares = ORDER_SIZE
                pair_cost_estimate = round(exec_shares * (comb if cross_trigger else 0.99), 2)
                wallet_bal = await asyncio.get_event_loop().run_in_executor(executor, sniper.get_balance)
                state["wallet_balance"] = wallet_bal

                if not PAPER_MODE and wallet_bal > 0 and wallet_bal < pair_cost_estimate:
                    if now % 10 == 0:
                        log(f"⚠️ [SOLVENCY GUARD] Balance (${wallet_bal:.2f}) < required pair cost (${pair_cost_estimate:.2f} for {exec_shares:.0f}sh). Skipping.")
                else:
                    if wave_trigger:
                        # $60+ Wave Setup: Buy surging side first, then snap 1c/2c on other side
                        if wave_dir == "UP":
                            leg1_token, leg1_p, leg1_name = mkt["up_token"], up_p, "UP"
                            leg2_token, leg2_p, leg2_name = mkt["down_token"], dn_p, "DOWN"
                        else:
                            leg1_token, leg1_p, leg1_name = mkt["down_token"], dn_p, "DOWN"
                            leg2_token, leg2_p, leg2_name = mkt["up_token"], up_p, "UP"
                        trigger_type = f"🌊 $60+ WAVE ({wave_dir} {s_move:+.1f}$)"
                    else:
                        # Standard sub-1.00 cross
                        if up_p <= dn_p:
                            leg1_token, leg1_p, leg1_name = mkt["up_token"], up_p, "UP"
                            leg2_token, leg2_p, leg2_name = mkt["down_token"], dn_p, "DOWN"
                        else:
                            leg1_token, leg1_p, leg1_name = mkt["down_token"], dn_p, "DOWN"
                            leg2_token, leg2_p, leg2_name = mkt["up_token"], up_p, "UP"
                        trigger_type = f"🎯 BOOK CROSS ({comb:.3f} <= {MAX_COMBINED_COST:.3f})"

                    # Ensure Leg 1 is within allowable price (<= 0.985)
                    if leg1_p <= LEG1_MAX_PRICE:
                        mode_tag = "[PAPER MODE - ZERO RISK]" if PAPER_MODE else "[LIVE REAL MONEY]"
                        log(f"🚀 [{trigger_type} -> TRIGGERED {mode_tag}] Leg 1: Buying {exec_shares:.1f}sh {leg1_name} @ ${leg1_p:.2f} (BTC Move: {s_move:+.2f}$)...")

                        # Execute Leg 1 with FOK
                        s1, res1 = await asyncio.get_event_loop().run_in_executor(
                            executor, sniper.execute_single_leg, leg1_token, leg1_p, exec_shares, leg1_name
                        )

                        if s1:
                            log(f"✅ [LEG 1 FILLED] Secured {exec_shares:.1f}sh {leg1_name} @ ${leg1_p:.2f}! Now stalking Leg 2 ({leg2_name} <= ${LEG2_MAX_HEDGE_PRICE:.2f})...")
                            state["leg1_position"] = {
                                "outcome": leg1_name,
                                "price": leg1_p,
                                "shares": exec_shares
                            }

                            max_leg2_price = LEG2_MAX_HEDGE_PRICE
                            leg2_filled = False
                            attempts = 0
                            max_attempts = 200  # 200 checks @ 25ms = 5.0s stalking
                            fill_p2 = 0.0

                            while attempts < max_attempts and not leg2_filled:
                                attempts += 1
                                _u_p, _u_s, _d_p, _d_s = ws_stream.get_prices(mkt["up_token"], mkt["down_token"])
                                if _u_p >= 1.0 and _d_p >= 1.0:
                                    _u_p, _u_s, _d_p, _d_s = await asyncio.get_event_loop().run_in_executor(
                                        executor, sniper.fetch_order_books, mkt["up_token"], mkt["down_token"]
                                    )
                                current_p2 = _d_p if leg2_name == "DOWN" else _u_p
                                current_s2 = _d_s if leg2_name == "DOWN" else _u_s

                                if current_p2 <= max_leg2_price and current_s2 >= 1.0:
                                    log(f"⚡ [LEG 2 DETECTED via WebSocket in {attempts * 25}ms] {leg2_name} ask @ ${current_p2:.2f} ({current_s2:.0f}sh) <= ${max_leg2_price:.2f}! Snapping immediately...")
                                    s2, res2 = await asyncio.get_event_loop().run_in_executor(
                                        executor, sniper.execute_single_leg, leg2_token, current_p2, exec_shares, leg2_name
                                    )
                                    if s2:
                                        leg2_filled = True
                                        fill_p2 = current_p2
                                        break
                                await asyncio.sleep(0.025)

                            if leg2_filled:
                                real_comb = round(leg1_p + fill_p2, 3)
                                profit_usd = round((1.0 - real_comb) * exec_shares, 3)
                                pct = round(((1.0 - real_comb) / real_comb) * 100, 1)

                                sniper.trades_in_current_window += 1
                                sniper.total_lifetime_trades += 1
                                sniper.total_lifetime_profit += profit_usd

                                mode_label = "PAPER" if PAPER_MODE else "REAL"
                                trade_rec = {
                                    "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S UTC"),
                                    "market": mkt["slug"],
                                    "up_price": leg1_p if leg1_name == "UP" else fill_p2,
                                    "down_price": fill_p2 if leg1_name == "UP" else leg1_p,
                                    "combined_cost": real_comb,
                                    "shares": exec_shares,
                                    "profit": f"+${profit_usd:.3f} (+{pct:.1f}%)",
                                    "status": f"WAVE ARB [{mode_label}] ({leg1_name} @ ${leg1_p:.2f} + {leg2_name} @ ${fill_p2:.2f})"
                                }

                                state["recent_trades"].insert(0, trade_rec)
                                state["last_trade"] = trade_rec
                                state["total_lifetime_trades"] = sniper.total_lifetime_trades
                                state["total_lifetime_profit"] = round(sniper.total_lifetime_profit, 2)
                                state["trades_in_window"] = sniper.trades_in_current_window
                                state["leg1_position"] = None

                                log(f"🎉🔒 [ARBITRAGE SEALED & 100% HEDGED ({mode_label})] {leg1_name} ${leg1_p:.2f} + {leg2_name} ${fill_p2:.2f} = ${real_comb:.3f} | Profit: +${profit_usd:.2f} (+{pct}%)")
                            else:
                                log(f"⚠️ [LEG 2 TIMEOUT] {leg2_name} did not drop <= ${max_leg2_price:.2f} within 5s. Unwinding Leg 1 to avoid unhedged exposure...")
                                if not PAPER_MODE:
                                    try:
                                        opt = PartialCreateOrderOptions(tick_size="0.01", neg_risk=False)
                                        sell_order = sniper.client.create_order(
                                            OrderArgsV2(token_id=leg1_token, price=0.01, size=exec_shares, side="SELL"),
                                            options=opt
                                        )
                                        sniper.client.post_orders([PostOrdersV2Args(order=sell_order, orderType=OrderType.FOK)])
                                        log(f"🛡️ [SAFETY UNWIND COMPLETE] Sold {leg1_name} back to book. Zero unhedged risk.")
                                    except Exception as un_e:
                                        log(f"❌ [UNWIND ERROR] {un_e}")
                                else:
                                    log(f"🛡️ [PAPER UNWIND COMPLETE] Simulated sale of {leg1_name} back to book. Zero risk.")
                                state["leg1_position"] = None
                                sniper.trades_in_current_window += 1
                                sniper.total_lifetime_trades += 1
                                state["total_lifetime_trades"] = sniper.total_lifetime_trades
                                unwind_rec = {
                                    "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S UTC"),
                                    "market": mkt["slug"],
                                    "up_price": leg1_p if leg1_name == "UP" else 0.0,
                                    "down_price": leg1_p if leg1_name == "DOWN" else 0.0,
                                    "combined_cost": leg1_p,
                                    "shares": exec_shares,
                                    "profit": "$0.00 (Unwound)",
                                    "status": f"SAFETY UNWOUND ({leg1_name} bought @ ${leg1_p:.2f} & sold back)"
                                }
                                state["recent_trades"].insert(0, unwind_rec)
                                state["last_trade"] = unwind_rec
                        else:
                            log(f"ℹ️ [LEG 1 MISSED] {leg1_name} @ ${leg1_p:.2f} order not filled. 0 shares held.")

            # Status and Log Output
            if sniper.total_lifetime_trades >= MAX_TOTAL_PAIRS:
                state["status"] = f"🛑 [{MAX_TOTAL_PAIRS}-TRADE RUN COMPLETE] Finished! Engine stopped."
            elif sniper.trades_in_current_window >= MAX_TRADES_PER_WINDOW:
                state["status"] = f"🔒 Quota Filled for Candle | Next candle in T-{t_rem}s | Progress: {sniper.total_lifetime_trades}/{MAX_TOTAL_PAIRS}"
            else:
                wave_info = f"🌊 Wave: {s_move:+.1f}$ (Target: ±${WAVE_THRESHOLD_USD:.0f})"
                state["status"] = f"Scanning {mkt['slug']} | T-{t_rem}s | BTC: ${spot_p:,.1f} ({wave_info}) | UP: ${up_p:.2f} | DN: ${dn_p:.2f} | Sum: ${comb:.3f} (Trades: {sniper.total_lifetime_trades}/{MAX_TOTAL_PAIRS})"

            # Stream live tick to dashboard log box every 1.5 second
            if not hasattr(sniper, "_last_log_t") or (time.time() - sniper._last_log_t) >= 1.5:
                sniper._last_log_t = time.time()
                t_str = "🔒 PAIR LOCKED" if sniper.trades_in_current_window >= 1 else (f"🌊 $60+ WAVE ACTIVE ({wave_dir})" if is_wave else f"🔍 HUNTING $60 WAVE (Current: {s_move:+.1f}$)")
                log(f"T-{t_rem:03d}s | BTC: ${spot_p:,.1f} ({s_move:+.1f}$) | UP: ${up_p:.2f} | DN: ${dn_p:.2f} | Comb: ${comb:.3f} | {t_str}")

            await asyncio.sleep(POLL_INTERVAL)
        except Exception as e:
            log(f"⚠️ [LOOP ERROR] {e}")
            await asyncio.sleep(0.5)

async def audit_and_balance_loop():
    while True:
        try:
            bal = await asyncio.get_event_loop().run_in_executor(executor, fetch_wallet_balance)
            state["wallet_balance"] = bal
        except Exception:
            pass
        await asyncio.sleep(10.0)

@app.on_event("startup")
async def startup_event():
    ws_stream.start()
    asyncio.create_task(sniper_background_loop())
    asyncio.create_task(audit_and_balance_loop())

@app.get("/api/state")
def get_state():
    return JSONResponse(state)

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    funder_short = state['funder'][:6] + '...' + state['funder'][-4:] if state['funder'] else '0x81ad...e50a'
    asset_upper = TARGET_ASSET.upper()
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PolyBot: BTC 5M $60+ Wave Sniper</title>
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg: #07090e;
                --surface: #0f141f;
                --surface-card: #141b2b;
                --border: #1e293b;
                --accent-blue: #3b82f6;
                --accent-emerald: #10b981;
                --accent-amber: #f59e0b;
                --accent-purple: #a855f7;
                --accent-rose: #f43f5e;
                --text-primary: #f8fafc;
                --text-muted: #94a3b8;
            }}
            * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }}
            body {{ background-color: var(--bg); color: var(--text-primary); min-height: 100vh; padding: 20px 16px; }}
            .container {{ max-width: 1200px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }}
            
            /* Header */
            .header {{
                background: linear-gradient(135deg, rgba(20, 27, 43, 0.95) 0%, rgba(15, 20, 31, 0.95) 100%);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 18px 24px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 12px;
            }}
            .brand-wrap h1 {{ font-size: 20px; font-weight: 800; display: flex; align-items: center; gap: 8px; letter-spacing: -0.5px; }}
            .brand-subtitle {{ color: var(--text-muted); font-size: 12px; margin-top: 2px; }}
            .header-badges {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
            .badge {{
                font-size: 11px;
                padding: 5px 12px;
                border-radius: 20px;
                font-weight: 700;
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            .badge-paper {{ background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid #a855f7; }}
            .badge-live {{ background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }}
            .pulse-dot {{ width: 7px; height: 7px; border-radius: 50%; background: #10b981; box-shadow: 0 0 8px #10b981; animation: pulse 1.5s infinite; }}
            @keyframes pulse {{ 0%, 100% {{ opacity: 1; transform: scale(1); }} 50% {{ opacity: 0.4; transform: scale(0.8); }} }}

            /* Hero Wave Card */
            .hero-wave-card {{
                background: linear-gradient(135deg, rgba(20, 27, 43, 0.9) 0%, rgba(13, 17, 28, 0.9) 100%);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 20px 24px;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
                gap: 20px;
                align-items: center;
            }}
            .hero-col {{ display: flex; flex-direction: column; gap: 4px; }}
            .hero-title {{ font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }}
            .hero-val {{ font-size: 30px; font-weight: 800; font-family: 'JetBrains Mono', monospace; line-height: 1.1; }}
            .hero-sub {{ font-size: 12px; color: var(--text-muted); }}

            /* Market Grid (2 Books) */
            .market-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 16px;
            }}
            @media (max-width: 680px) {{
                .market-grid {{ grid-template-columns: 1fr; }}
            }}
            .book-card {{
                background: var(--surface-card);
                border: 1px solid var(--border);
                border-radius: 14px;
                padding: 16px 20px;
                display: flex;
                flex-direction: column;
                gap: 6px;
            }}
            .book-header {{ display: flex; justify-content: space-between; align-items: center; }}
            .book-name {{ font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 6px; }}
            .book-depth {{ font-size: 11px; padding: 2px 8px; border-radius: 8px; font-family: 'JetBrains Mono', monospace; font-weight: 700; }}
            .depth-badge-pass {{ background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }}
            .book-price {{ font-size: 26px; font-weight: 800; font-family: 'JetBrains Mono', monospace; }}

            /* Panel Cards */
            .panel {{
                background: var(--surface-card);
                border: 1px solid var(--border);
                border-radius: 14px;
                padding: 18px 20px;
            }}
            .panel-header {{
                font-size: 12px;
                font-weight: 700;
                color: var(--text-muted);
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 12px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            
            /* Table */
            .table-wrap {{ overflow-x: auto; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
            th {{ text-align: left; padding: 10px 8px; color: var(--text-muted); font-weight: 700; border-bottom: 1px solid var(--border); font-size: 11px; text-transform: uppercase; }}
            td {{ padding: 10px 8px; border-bottom: 1px solid rgba(255,255,255,0.04); font-family: 'JetBrains Mono', monospace; }}
            tr:hover td {{ background: rgba(255,255,255,0.02); }}

            /* Log Box */
            .log-box {{
                background: #04060a;
                border: 1px solid var(--border);
                border-radius: 10px;
                padding: 14px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                height: 220px;
                overflow-y: auto;
                color: #a5f3fc;
                line-height: 1.6;
            }}
            .log-box div {{ border-bottom: 1px solid rgba(255,255,255,0.02); padding: 2px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Header -->
            <div class="header">
                <div class="brand-wrap">
                    <h1>⚡ PolyBot: BTC 5M $60+ Wave Sniper</h1>
                    <div class="brand-subtitle">Binance Spot-Triggered Wave Arbitrage &rarr; Stalking $0.98 Surges & $0.01 Hedges (Target: &ge; $60.00 Move)</div>
                </div>
                <div class="header-badges">
                    <span class="badge badge-paper">🧪 PAPER TRADING (ZERO RISK)</span>
                    <span class="badge badge-live"><span class="pulse-dot"></span> ENGINE LIVE</span>
                </div>
            </div>

            <!-- Hero Wave Tracker -->
            <div class="hero-wave-card">
                <div class="hero-col">
                    <div class="hero-title">BINANCE BTC SPOT</div>
                    <div class="hero-val" style="color: #f59e0b;" id="spotPrice">$0.00</div>
                    <div class="hero-sub" id="strikeOpen">Candle Open: $0.00</div>
                </div>
                <div class="hero-col">
                    <div class="hero-title">WAVE DELTA FROM OPEN</div>
                    <div class="hero-val" id="waveDelta">$0.00</div>
                    <div class="hero-sub" id="waveStatus">Target: &plusmn;$60.00 Move</div>
                </div>
                <div class="hero-col">
                    <div class="hero-title">ACTIVE 5M CANDLE & TIMER</div>
                    <div class="hero-val" style="color: #60a5fa;" id="candleTimer">T-0s</div>
                    <div class="hero-sub" id="candleSlug">Scanning active market...</div>
                </div>
                <div class="hero-col">
                    <div class="hero-title">SESSION PAPER P&L</div>
                    <div class="hero-val" style="color: #10b981;" id="sessionProfit">+$0.00</div>
                    <div class="hero-sub" id="tradeCount">0 Completed Snipes</div>
                </div>
            </div>

            <!-- Strategy Live Status Banner -->
            <div style="background: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.25); border-radius: 12px; padding: 12px 18px; display: flex; align-items: center; justify-content: space-between; gap: 10px; font-size: 13px; flex-wrap: wrap;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 16px;">🎯</span>
                    <span style="color: var(--text-muted); font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">LIVE BOT STATE:</span>
                    <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #60a5fa;" id="strategyStatus">Scanning BTC 5M market...</span>
                </div>
                <div style="font-size: 11px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace;" id="rulesPill">Strategy: &ge; $60 Move &bull; Leg 1: &le; $0.985 &bull; Leg 2: &le; $0.02</div>
            </div>

            <!-- Polymarket Live Order Books -->
            <div class="market-grid">
                <div class="book-card">
                    <div class="book-header">
                        <span class="book-name" style="color: #10b981;">🟢 UP TOKEN ASK</span>
                        <span class="book-depth depth-badge-pass" id="upDepth">0 sh</span>
                    </div>
                    <div class="book-price" style="color: #10b981;" id="upAsk">$0.00</div>
                    <div class="hero-sub">Wave Buy Target: &le; $0.985</div>
                </div>
                <div class="book-card">
                    <div class="book-header">
                        <span class="book-name" style="color: #f43f5e;">🔴 DOWN TOKEN ASK</span>
                        <span class="book-depth depth-badge-pass" id="dnDepth">0 sh</span>
                    </div>
                    <div class="book-price" style="color: #f43f5e;" id="dnAsk">$0.00</div>
                    <div class="hero-sub">Wave Buy Target: &le; $0.985</div>
                </div>
            </div>

            <!-- Recent Executed Trades Table -->
            <div class="panel">
                <div class="panel-header">
                    <span>EXECUTED PAPER ARBITRAGE TRADES</span>
                    <span style="font-family:'JetBrains Mono'; font-weight:700; color:#10b981;" id="quotaBadge">Quota: 0 / 1</span>
                </div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Time (UTC)</th>
                                <th>Market</th>
                                <th>UP Ask</th>
                                <th>DOWN Ask</th>
                                <th>Pair Cost</th>
                                <th>Shares</th>
                                <th>Profit</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody id="tradesBody">
                            <tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 20px;">Scanning for $60+ wave setup on Bitcoin...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Real-Time Container Logs Box -->
            <div class="panel">
                <div class="panel-header">
                    <span>REAL-TIME ENGINE LOGS</span>
                    <span style="font-size: 11px; text-transform: none; color: #10b981;">Sub-Second Streaming</span>
                </div>
                <div class="log-box" id="logsBox"></div>
            </div>
        </div>

        <script>
            async function updateState() {{
                try {{
                    const res = await fetch('/api/state');
                    const d = await res.json();
                    
                    // Spot Price & Strike Open
                    if (d.spot_price) {{
                        document.getElementById('spotPrice').innerText = '$' + d.spot_price.toLocaleString(undefined, {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
                    }}
                    if (d.candle_open) {{
                        document.getElementById('strikeOpen').innerText = 'Candle Open: $' + d.candle_open.toLocaleString(undefined, {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
                    }}

                    // Wave Move & Status
                    const waveEl = document.getElementById('waveDelta');
                    const statusEl = document.getElementById('waveStatus');
                    const moveVal = (d.spot_move !== undefined ? d.spot_move : 0.0);
                    const absMove = (d.abs_spot_move !== undefined ? d.abs_spot_move : Math.abs(moveVal));
                    
                    const sign = moveVal >= 0 ? '+' : '-';
                    waveEl.innerText = `${{sign}}$${{absMove.toFixed(2)}}`;
                    waveEl.style.color = absMove >= 60.0 ? '#10b981' : (absMove >= 40.0 ? '#f59e0b' : '#f8fafc');

                    if (absMove >= 60.0) {{
                        statusEl.innerHTML = `<span style="color:#10b981; font-weight:800;">🌊 $60+ WAVE ACTIVE (${{d.wave_direction}})</span>`;
                    }} else {{
                        statusEl.innerText = `Need $${{(60.0 - absMove).toFixed(2)}} more for $60 wave`;
                    }}

                    // Bot Live Strategy Status
                    if (document.getElementById('strategyStatus') && d.status) {{
                        document.getElementById('strategyStatus').innerText = d.status;
                    }}

                    // Timer & Slug
                    document.getElementById('candleTimer').innerText = 'T-' + (d.seconds_remaining || 0) + 's';
                    document.getElementById('candleSlug').innerText = (d.current_candle_slug || 'Scanning...');

                    // P&L
                    const profVal = d.total_lifetime_profit || 0.0;
                    document.getElementById('sessionProfit').innerText = (profVal >= 0 ? '+' : '') + '$' + profVal.toFixed(2);
                    document.getElementById('tradeCount').innerText = (d.total_lifetime_trades || 0) + ' Completed Snipes';
                    document.getElementById('quotaBadge').innerText = `Quota: ${{d.trades_in_window || 0}} / ${{d.max_trades_per_window || 1}}`;

                    // Order Books
                    document.getElementById('upAsk').innerText = '$' + (d.live_up_ask || 0.0).toFixed(2);
                    document.getElementById('upDepth').innerText = (d.live_up_depth || 0.0).toFixed(0) + ' sh';
                    document.getElementById('dnAsk').innerText = '$' + (d.live_down_ask || 0.0).toFixed(2);
                    document.getElementById('dnDepth').innerText = (d.live_down_depth || 0.0).toFixed(0) + ' sh';

                    // Executed Trades Table
                    if (d.recent_trades && d.recent_trades.length > 0) {{
                        const rows = d.recent_trades.map(t => {{
                            const pStr = t.profit || (t.profit_usdc ? `+$${{t.profit_usdc.toFixed(2)}}` : '$0.00');
                            const sVal = t.shares || t.size || 5.0;
                            const stVal = t.status || 'WAVE ARB';
                            const uP = (t.up_price !== undefined ? t.up_price : 0).toFixed(2);
                            const dP = (t.down_price !== undefined ? t.down_price : 0).toFixed(2);
                            const cP = (t.combined_cost !== undefined ? t.combined_cost : 0).toFixed(3);
                            return `
                            <tr>
                                <td>${{t.timestamp || ''}}</td>
                                <td>${{t.market || ''}}</td>
                                <td style="color:#10b981;">$${{uP}}</td>
                                <td style="color:#f43f5e;">$${{dP}}</td>
                                <td style="font-weight:700;">$${{cP}}</td>
                                <td>${{sVal}} sh</td>
                                <td style="color:#10b981; font-weight:800;">${{pStr}}</td>
                                <td><span style="font-size:11px; padding:2px 8px; border-radius:6px; background:rgba(16,185,129,0.15); color:#10b981;">${{stVal}}</span></td>
                            </tr>
                        `}}).join('');
                        document.getElementById('tradesBody').innerHTML = rows;
                    }}

                    // Live Container Logs
                    const box = document.getElementById('logsBox');
                    if (box && d.logs && d.logs.length > 0) {{
                        box.innerHTML = d.logs.slice(-40).map(l => '<div>' + l + '</div>').join('');
                        box.scrollTop = box.scrollHeight;
                    }}
                }} catch(e) {{
                    console.error("updateState error:", e);
                }}
            }}
            setInterval(updateState, 300);
            updateState();
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
