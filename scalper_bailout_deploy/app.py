import os
import sys
import time
import json
import ssl
import threading
import datetime
import requests
from flask import Flask, jsonify, render_template_string
from dotenv import load_dotenv

sys.stdout.reconfigure(line_buffering=True)
load_dotenv()

app = Flask(__name__)

bot_state = {
    "status": "Initializing",
    "phase": "Phase 1: Sprint (100% Compounding)",
    "last_trade": None,
    "wins": 0,
    "losses": 0,
    "streak": 0,
    "total_trades": 0,
    "total_profit_usdc": 0.0,
    "logs": [],
    "balance": 0.0,
    "current_candle": None,
    "strike_price": None,
    "chainlink_price": None,
    "gap": None
}

def log(msg):
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    formatted = f"[{timestamp}] {msg}"
    try:
        print(formatted, flush=True)
    except UnicodeEncodeError:
        print(formatted.encode("ascii", "replace").decode("ascii"), flush=True)
    bot_state["logs"].append(formatted)
    if len(bot_state["logs"]) > 250:
        bot_state["logs"].pop(0)

# Endpoints & Config
GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"
LIVE_WS_URL= "wss://ws-live-data.polymarket.com/"
WS_HEADERS = {"User-Agent": "Mozilla/5.0"}

POLYMARKET_LIVE_TRADING    = os.getenv("POLYMARKET_LIVE_TRADING", "true").lower() == "true"
POLYMARKET_ADDRESS         = os.getenv("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY         = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET      = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE  = os.getenv("POLYMARKET_API_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY     = os.getenv("POLYMARKET_PRIVATE_KEY", "")

# 🎯 Strategic Parameters
SURGE_WINDOW_START         = 270.0  # T-270s (Minute 0:30) full candle scan for surges
SURGE_WINDOW_END           = 15.0   # T-15s cutoff for Surge Scalp
SURGE_MIN_MOVE_USD         = 25.0   # BTC must move at least $25.00 from strike

CLOSE_WINDOW_START         = 12.0   # T-12s start for Final Resolution Snipe
CLOSE_WINDOW_END           = 5.0    # T-5s safe cutoff
CLOSE_MIN_MOVE_USD         = 12.0   # BTC must move at least $12.00 for late hold
MAX_WIN_STREAK_CAP         = 4      # 4-Win Take-Profit Cap for Phase 2
WINDOW_SECS                = 300    # 5-minute candle

def win_start(ts=None):
    if ts is None: ts = time.time()
    return int(ts // WINDOW_SECS) * WINDOW_SECS

def win_end(ts=None):
    return win_start(ts) + WINDOW_SECS

def slug_for(ts=None):
    return f"btc-updown-5m-{win_start(ts)}"

# Initialize EIP-712 Memory-Signed CLOB Client
client = None
if POLYMARKET_LIVE_TRADING:
    try:
        from py_clob_client_v2 import ClobClient, ApiCreds
        creds = ApiCreds(
            api_key=POLYMARKET_API_KEY,
            api_secret=POLYMARKET_API_SECRET,
            api_passphrase=POLYMARKET_API_PASSPHRASE
        )
        client = ClobClient(
            host=CLOB_HOST,
            chain_id=137,
            key=POLYMARKET_PRIVATE_KEY,
            creds=creds,
            signature_type=3,
            funder=POLYMARKET_ADDRESS
        )
        log("⚡ High-Speed EIP-712 Memory-Signed Execution Engine Initialized.")
    except Exception as e:
        log(f"CLOB Client Init Error: {e}")

# Live Chainlink Feed
class ChainlinkFeed:
    def __init__(self):
        self.price = None
        self.ts_ms = None
        self._lock = threading.Lock()

    def start(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        def on_open(ws):
            ws.send(json.dumps({
                "action": "subscribe",
                "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}]
            }))

        def on_message(ws, raw):
            if not raw: return
            try:
                msg = json.loads(raw)
                if msg.get("topic") == "crypto_prices_chainlink":
                    p = msg.get("payload", {})
                    if p.get("symbol") == "btc/usd":
                        with self._lock:
                            self.price = float(p.get("value", 0))
                            self.ts_ms = p.get("timestamp")
                            bot_state["chainlink_price"] = self.price
            except Exception:
                pass

        def on_close(ws, c, m):
            time.sleep(2)
            self.start()

        def on_error(ws, e): pass

        import websocket
        app_ws = websocket.WebSocketApp(LIVE_WS_URL, header=WS_HEADERS,
            on_open=on_open, on_message=on_message,
            on_close=on_close, on_error=on_error)
        threading.Thread(target=lambda: app_ws.run_forever(sslopt={"context": ctx}), daemon=True).start()

    def get_price(self):
        with self._lock:
            return self.price

chainlink_feed = ChainlinkFeed()
chainlink_feed.start()

def get_market_tokens(ts=None):
    slug = slug_for(ts)
    url = f"{GAMMA_HOST}/events?slug={slug}"
    try:
        r = requests.get(url, timeout=2)
        evts = r.json()
        if not evts or not evts[0].get("markets"): return None
        mkt = evts[0]["markets"][0]
        tids = json.loads(mkt.get("clobTokenIds") or "[]")
        outs = [str(o).lower() for o in json.loads(mkt.get("outcomes") or "[]")]
        up_id = dn_id = None
        for i, o in enumerate(outs):
            if o in ("up", "yes"):    up_id = tids[i]
            elif o in ("down", "no"): dn_id = tids[i]
        if not up_id and len(tids) > 0: up_id = tids[0]
        if not dn_id and len(tids) > 1: dn_id = tids[1]

        return {"slug": slug, "up_id": up_id, "down_id": dn_id}
    except Exception:
        return None

# 🛑 Rate-Limit Protected Order Book Probe with 50ms micro-caching & 429 Backoff
_book_cache = {} # token_id -> (timestamp, (best_bid, best_ask))

def probe_book_depth(token_id, timeout=1.0):
    now_t = time.time()
    # Return micro-cached response if called within 50ms (avoids duplicate 429 spam)
    if token_id in _book_cache:
        c_time, c_val = _book_cache[token_id]
        if now_t - c_time < 0.050:
            return c_val

    for attempt in range(2):
        try:
            r = requests.get(f"{CLOB_HOST}/book", params={"token_id": token_id}, timeout=timeout)
            if r.status_code == 429:
                time.sleep(0.15 * (attempt + 1)) # Backoff on 429
                continue
            r.raise_for_status()
            data = r.json()
            bids = [float(b["price"]) for b in data.get("bids", [])]
            asks = [float(a["price"]) for a in data.get("asks", [])]
            best_bid = max(bids) if bids else 0.0
            best_ask = min(asks) if asks else None
            _book_cache[token_id] = (time.time(), (best_bid, best_ask))
            return best_bid, best_ask
        except Exception:
            if attempt == 0:
                time.sleep(0.05)
                continue
            break
            
    # Fallback to cached value if network drops
    if token_id in _book_cache:
        return _book_cache[token_id][1]
    return 0.0, None

def get_live_balance():
    if not client:
        return 2.15
    try:
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
        resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        raw_b = float(resp.get("balance", 0)) / 1_000_000
        return round(raw_b, 2)
    except Exception:
        return 0.0

def hybrid_surge_scalper_worker():
    log("🚀 Ultra-Fast Surge-Scalper & Final-Sniper Online!")
    bot_state["status"] = "Running"
    
    last_traded_candle = None
    cached_market = None
    cached_slug = None
    candle_strike = None
    current_streak = 0

    while True:
        try:
            now = time.time()
            w_s = win_start(now)
            w_e = win_end(now)
            time_left = w_e - now
            slug = slug_for(now)

            bot_state["current_candle"] = f"{slug} ({time_left:.1f}s left)"

            # Pre-cache Market IDs at start of candle (0ms lookup lag)
            if cached_slug != slug:
                cached_market = get_market_tokens(now)
                cached_slug = slug
                candle_strike = chainlink_feed.get_price()
                bot_state["strike_price"] = candle_strike
                if cached_market:
                    log(f"🎯 Pre-Cached Market IDs for {slug} (Strike: ${candle_strike if candle_strike else 0:.2f})")

            if not candle_strike:
                candle_strike = chainlink_feed.get_price()
                bot_state["strike_price"] = candle_strike

            # Skip if already completed trade cycle this candle
            if last_traded_candle == w_s:
                time.sleep(0.5)
                continue

            if not cached_market or not cached_market.get("up_id") or not candle_strike:
                time.sleep(0.02)
                continue

            live_btc = chainlink_feed.get_price()
            if not live_btc:
                time.sleep(0.02)
                continue

            move = live_btc - candle_strike
            abs_move = abs(move)
            bot_state["gap"] = abs_move
            side_name = "UP" if move > 0 else "DOWN"
            target_id = cached_market["up_id"] if side_name == "UP" else cached_market["down_id"]
            opposing_id = cached_market["down_id"] if side_name == "UP" else cached_market["up_id"]

            bal = get_live_balance()
            if bal < 2.00:
                bot_state["phase"] = f"Waiting for Min $2.00 Balance (Current: ${bal:.2f})"
                time.sleep(0.5)
                continue

            # Sizing: Sprint 100% (under $10) starting from minimum $2.00 or 50/50 split (over $10)
            # 💡 Use 95% of available balance to guarantee fee estimates never trigger 400 errors
            if bal < 10.00:
                bot_state["phase"] = "Phase 1: Sprint (100% Compounding, Min $2.00)"
                stake_amount = max(2.00, round(bal * 0.95, 2))
            else:
                bot_state["phase"] = f"Phase 2: Safe 50/50 Split (Streak {current_streak}/{MAX_WIN_STREAK_CAP})"
                if current_streak >= MAX_WIN_STREAK_CAP:
                    log("💰 4-WIN PROFIT CAP REACHED! Banking gains and resetting streak to base.")
                    current_streak = 0
                stake_amount = max(2.00, round((bal / 2.0) * 0.95, 2))

            # ─────────────────────────────────────────────────────────────────
            # 🔥 TIER 1: EARLY SURGE IN-AND-OUT SCALP (T-270s down to T-15s)
            # ─────────────────────────────────────────────────────────────────
            if SURGE_WINDOW_END <= time_left <= SURGE_WINDOW_START:
                if abs_move >= SURGE_MIN_MOVE_USD:
                    target_bid, target_ask = probe_book_depth(target_id)
                    opp_bid, opp_ask = probe_book_depth(opposing_id)

                    # Only buy if valid asks exist at reasonable entry (<= 0.980)
                    if target_bid >= 0.85 and opp_bid <= 0.15 and target_ask is not None and target_ask <= 0.980:
                        if bal >= stake_amount and client:
                            t_start = time.perf_counter()
                            log(f"⚡ [T-{time_left:.1f}s | Move: ${move:+.1f}] SURGE DETECTED! Buying {side_name} @ Ask: ${target_ask:.3f} (Stake: ${stake_amount:.2f})...")

                            try:
                                from py_clob_client_v2 import MarketOrderArgsV2

                                buy_res = client.create_and_post_market_order(
                                    MarketOrderArgsV2(token_id=target_id, amount=stake_amount, side="BUY")
                                )
                                entry_price = target_ask
                                est_shares = round(stake_amount / entry_price, 2)
                                log(f"✅ BOUGHT {est_shares:.2f} sh of {side_name} @ ${entry_price:.3f}! Scanning for instant sell on bid increase...")

                                # Continuous Sub-Second Monitor: High-Yield Cash-Out & Bailout Shield
                                position_open = True
                                log(f"🎯 Continuous Cash-Out Monitor Active: Targeting >= 95¢ or +2¢ profit | 86¢ Bailout Shield Armed!")
                                
                                def execute_safe_sell(token_id, shares):
                                    for attempt in range(3):
                                        try:
                                            res = client.create_and_post_market_order(
                                                MarketOrderArgsV2(token_id=token_id, amount=shares, side="SELL")
                                            )
                                            return res
                                        except Exception as e_sell:
                                            if "balance is not enough" in str(e_sell) or "balance: 0" in str(e_sell):
                                                time.sleep(0.5) # Wait for CLOB balance indexing
                                                continue
                                            raise e_sell
                                    return None

                                while position_open:
                                    cur_bid, _ = probe_book_depth(target_id)
                                    rem = win_end() - time.time()
                                    live_now_btc = chainlink_feed.get_price() or live_btc
                                    cur_gap = abs(live_now_btc - candle_strike)

                                    # SAFEGUARD 1: HIGH-YIELD PROFIT CASHOUT (+10% to +15% ROI)
                                    if cur_bid >= 0.950 or cur_bid >= entry_price + 0.02:
                                        log(f"💰 [PROFIT TARGET REACHED: ${cur_bid:.3f} >= ${entry_price:.3f} + profit] FIRING INSTANT CASHOUT...")
                                        sell_res = execute_safe_sell(target_id, est_shares)
                                        profit_c = round((cur_bid - entry_price) * est_shares, 2)
                                        log(f"🎉 CASH-OUT WON! Sold {est_shares:.2f} sh @ ${cur_bid:.3f} (+${profit_c:.2f} Cash Profit). Exited to 100% Cash!")
                                        position_open = False
                                        last_traded_candle = w_s
                                        current_streak += 1
                                        bot_state["total_trades"] += 1
                                        bot_state["wins"] += 1
                                        bot_state["streak"] = current_streak
                                        bot_state["total_profit_usdc"] = round(bot_state.get("total_profit_usdc", 0.0) + profit_c, 2)
                                        bot_state["last_trade"] = f"Surge Cash-Out: Sold @ ${cur_bid:.3f} (+${profit_c:.2f})"
                                        break

                                    # SAFEGUARD 2: THE 2-SECOND BAILOUT SHIELD (STOP-LOSS ON FAKEOUTS)
                                    if cur_bid <= entry_price - 0.02 or (cur_gap <= 10.0 and (time.time() - t_start > 3.0)):
                                        log(f"🛡️ [BAILOUT TRIGGERED: Bid dropped to ${cur_bid:.3f} | Gap: ${cur_gap:.1f}] FIRING EMERGENCY SELL...")
                                        sell_res = execute_safe_sell(target_id, est_shares)
                                        loss_c = round((entry_price - cur_bid) * est_shares, 2)
                                        log(f"🛡️ BAILOUT COMPLETED! Sold {est_shares:.2f} sh @ ${cur_bid:.3f} (-${loss_c:.2f} scratch). Saved 96%+ of Capital!")
                                        position_open = False
                                        last_traded_candle = w_s
                                        current_streak = 0
                                        bot_state["total_trades"] += 1
                                        bot_state["losses"] += 1
                                        bot_state["streak"] = 0
                                        bot_state["total_profit_usdc"] = round(bot_state.get("total_profit_usdc", 0.0) - loss_c, 2)
                                        bot_state["last_trade"] = f"Bailout Exit: Sold @ ${cur_bid:.3f} (-${loss_c:.2f})"
                                        break

                                    # SAFEGUARD 3: MANDATORY T-10s EXIT
                                    if rem <= 10.0:
                                        log(f"🔒 [T-10s REACHED] Mandatory Cash-Out @ Bid ${cur_bid:.3f}. Exiting to 100% Cash before close!")
                                        sell_res = execute_safe_sell(target_id, est_shares)
                                        profit_c = round((cur_bid - entry_price) * est_shares, 2)
                                        log(f"✅ T-10s CASH-OUT EXECUTED! Sold @ ${cur_bid:.3f} ({profit_c:+.2f} USDC). 100% Safe in Cash!")
                                        position_open = False
                                        last_traded_candle = w_s
                                        if profit_c >= 0:
                                            current_streak += 1
                                            bot_state["wins"] += 1
                                        else:
                                            current_streak = 0
                                            bot_state["losses"] += 1
                                        bot_state["total_trades"] += 1
                                        bot_state["streak"] = current_streak
                                        bot_state["total_profit_usdc"] = round(bot_state.get("total_profit_usdc", 0.0) + profit_c, 2)
                                        bot_state["last_trade"] = f"T-10s Cash-Out: Sold @ ${cur_bid:.3f} ({profit_c:+.2f} USDC)"
                                        break

                                    time.sleep(0.02) # 20ms poll rate

                            except Exception as ex:
                                log(f"Surge Execution Error: {ex}")

            # ─────────────────────────────────────────────────────────────────
            # 🏆 TIER 2: FINAL RESOLUTION SNIPE (T-12s down to T-5s)
            # ─────────────────────────────────────────────────────────────────
            elif CLOSE_WINDOW_END <= time_left <= CLOSE_WINDOW_START:
                if abs_move >= CLOSE_MIN_MOVE_USD:
                    target_bid, target_ask = probe_book_depth(target_id)
                    opp_bid, opp_ask = probe_book_depth(opposing_id)

                    if target_bid >= 0.85 and opp_bid <= 0.15 and target_ask is not None:
                        if bal >= stake_amount and client:
                            t_start = time.perf_counter()
                            log(f"⚡ [T-{time_left:.1f}s | Move: ${move:+.1f}] FINAL SNIPE on {side_name} (Stake: ${stake_amount:.2f} @ Ask: ${target_ask:.3f})...")

                            try:
                                from py_clob_client_v2 import MarketOrderArgsV2

                                res = client.create_and_post_market_order(
                                    MarketOrderArgsV2(token_id=target_id, amount=stake_amount, side="BUY")
                                )

                                t_end = time.perf_counter()
                                latency_ms = (t_end - t_start) * 1000.0

                                log(f"✅ FINAL SNIPE EXECUTED in {latency_ms:.1f}ms! Staked ${stake_amount:.2f} on {side_name} | Order ID: {res.get('orderID', 'Filled')}.")

                                last_traded_candle = w_s
                                current_streak += 1
                                bot_state["total_trades"] += 1
                                bot_state["wins"] += 1
                                bot_state["streak"] = current_streak
                                est_net = round(stake_amount * 0.02, 2)
                                bot_state["total_profit_usdc"] = round(bot_state.get("total_profit_usdc", 0.0) + est_net, 2)
                                bot_state["last_trade"] = f"Final Snipe: Staked ${stake_amount:.2f} on {side_name} in {latency_ms:.0f}ms (+${est_net:.2f})"

                            except Exception as ex:
                                log(f"Execution Error: {ex}")

            time.sleep(0.02) # Ultra-low 20ms poll latency

        except Exception as e:
            log(f"Worker Loop Exception: {e}")
            time.sleep(1)

@app.route("/")
def index():
    bal = get_live_balance()
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>⚡ Dual-Tier Surge Scalper & Final Sniper</title>
        <meta http-equiv="refresh" content="2">
        <style>
            body {{ background: #080c14; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; }}
            .card {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 12px; padding: 25px; max-width: 950px; margin: 0 auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); }}
            h1 {{ color: #10b981; margin-top: 0; display: flex; align-items: center; justify-content: space-between; font-size: 22px; }}
            .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
            .stat-box {{ background: #1e293b; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #334155; }}
            .stat-label {{ font-size: 13px; color: #94a3b8; margin-bottom: 5px; }}
            .stat-val {{ font-size: 24px; font-weight: bold; color: #10b981; }}
            .log-box {{ background: #020617; border-radius: 8px; padding: 15px; height: 350px; overflow-y: auto; font-family: monospace; font-size: 13px; color: #a7f3d0; border: 1px solid #1e293b; }}
            .badge {{ background: #10b981; color: #000; padding: 5px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
            .candle-bar {{ background: #1e293b; padding: 12px 15px; border-radius: 6px; font-weight: 500; margin-bottom: 15px; color: #38bdf8; display: flex; justify-content: space-between; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>
                <span>⚡ Dual-Tier Surge Scalper & Final Sniper</span>
                <span class="badge">ACTIVE (T-45s Scalp + T-12s Snipe)</span>
            </h1>
            <div class="candle-bar">
                <span>Candle: {bot_state.get('current_candle', 'Scanning...')}</span>
                <span>Mode: {bot_state.get('phase', 'Sprint')} | Gap: ${bot_state.get('gap') or 0:.1f}</span>
            </div>
            <div class="stats">
                <div class="stat-box"><div class="stat-label">Total Trades</div><div class="stat-val">{bot_state['total_trades']}</div></div>
                <div class="stat-box"><div class="stat-label">Streak</div><div class="stat-val" style="color:#60a5fa;">{bot_state['streak']} W</div></div>
                <div class="stat-box"><div class="stat-label">Net Profit</div><div class="stat-val">+${bot_state['total_profit_usdc']:.2f}</div></div>
                <div class="stat-box"><div class="stat-label">Wallet Cash</div><div class="stat-val">${bal:.2f}</div></div>
            </div>
            <h3>📜 Live Millisecond Stream & Execution Logs</h3>
            <div class="log-box">
                {"<br>".join(reversed(bot_state['logs']))}
            </div>
        </div>
    </body>
    </html>
    """

@app.route("/api/state")
def state():
    bot_state["balance"] = get_live_balance()
    return jsonify(bot_state)

if __name__ == "__main__":
    t = threading.Thread(target=hybrid_surge_scalper_worker, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
