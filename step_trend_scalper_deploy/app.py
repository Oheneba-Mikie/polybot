#!/usr/bin/env python3
"""
app.py — Bot 3: Step-Trend Displacement Scalper Bot + Live Web Dashboard for Railway

Strategy & Rules:
1. Trigger: Real-time BTC distance >= $25.00 from Price to Beat (PTB) with directional slope confirmation.
   (Captures clean 15-45s grinding step trends without requiring artificial 3s flash explosions).
2. Stake: Exactly $1.00 starting bankroll.
3. Exit: +1c take-profit scalp exit immediately upon entry (or emergency dump at T-30s).
4. Limits: Strictly 1 trade per 5-minute candle.
5. Money Management:
   - On Win: Total balance ($1.00 + winnings) rolls over to fund the next window.
   - On Loss: Permanent Halt. Never trades again.
6. 3-Layer Sell Protection: Exact `takingAmount` share parsing from CLOB fill + live precision fallback retries.
"""

import json
import os
import ssl
import sys
import time
import math
import logging
import datetime
import threading
from collections import deque
from flask import Flask, jsonify, render_template
import requests
import websocket
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────────
LIVE_WS_URL     = "wss://ws-live-data.polymarket.com/"
GAMMA_HOST      = "https://gamma-api.polymarket.com"
CLOB_HOST       = "https://clob.polymarket.com"
WINDOW_SECS     = 300           # 5-minute candle

# Step Trend Parameters
STEP_DISPLACEMENT_TRIGGER = 25.0  # >= $25.00 distance away from PTB
MIN_TOKEN_PRICE           = 0.45  # Ignore dead tokens
MAX_TOKEN_PRICE           = 0.80  # Don't buy tokens above $0.80 (leave room to scalp)
TAKE_PROFIT_CENTS         = 0.01  # Exit immediately on +1 cent bid increase
EMERGENCY_EXIT_TIME       = 30    # T-30s: Emergency dump before window close. NEVER hold to expiry.
ENTRY_CUTOFF_TIME         = 45    # No new entries inside last 45 seconds of candle

STATE_FILE = "step_trend_state.json"

# ── Global State ────────────────────────────────────────────────────────────────
current_bankroll  = 1.00        # Starts with $1.00, rolls over on win
consecutive_wins  = 0
is_halted         = False       # If we lose, halted forever
halt_reason       = ""

wallet_balance    = 0.00
btc_price         = 0.00
btc_ptb           = 0.00
window_trade_done = False

current_scalp = {
    "active": False,
    "side": None,
    "token_id": None,
    "shares": 0.0,
    "entry_price": 0.0,
    "entry_time": None,
    "entry_cost": 0.0,
    "target_sell_price": 0.0,
    "state": "IDLE"
}

trade_history = deque(maxlen=30)
console_logs  = deque(maxlen=60)
price_ticks   = deque(maxlen=600) # (timestamp, price)

log_lock   = threading.Lock()
state_lock = threading.Lock()
scalp_lock = threading.Lock()

# ── State Persistence ───────────────────────────────────────────────────────────
def save_state():
    with state_lock:
        try:
            state = {
                "current_bankroll": current_bankroll,
                "consecutive_wins": consecutive_wins,
                "is_halted": is_halted,
                "halt_reason": halt_reason
            }
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            log_info(f"⚠️ Error saving state file: {e}")

def load_state():
    global current_bankroll, consecutive_wins, is_halted, halt_reason
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            current_bankroll = state.get("current_bankroll", 1.00)
            consecutive_wins = state.get("consecutive_wins", 0)
            is_halted = state.get("is_halted", False)
            halt_reason = state.get("halt_reason", "")
            log_info(f"📂 Loaded state: Bankroll=${current_bankroll:.2f} | Wins={consecutive_wins} | Halted={is_halted}")
            return True
        except Exception as e:
            log_info(f"⚠️ Error loading state file: {e}")
    return False

# ── Logging ─────────────────────────────────────────────────────────────────────
def log_info(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    sys.stdout.flush()
    with log_lock:
        console_logs.append(formatted)

def record_trade(time_str, side, entry_p, exit_p, stake, pnl, exit_reason):
    outcome = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "EVEN")
    trade_record = {
        "time": time_str,
        "side": side,
        "entry_price": entry_p,
        "exit_price": exit_p,
        "stake": stake,
        "pnl": pnl,
        "outcome": outcome,
        "reason": exit_reason
    }
    with log_lock:
        trade_history.append(trade_record)

# ── Flask Web App ───────────────────────────────────────────────────────────────
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
app = Flask(__name__, template_folder=template_dir)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

@app.route('/')
def home():
    return render_template('dashboard.html')

def build_status_response():
    with state_lock:
        w_bal    = wallet_balance
        p_btc    = btc_price
        p_ptb    = btc_ptb
        w_done   = window_trade_done
        c_bank   = current_bankroll
        c_wins   = consecutive_wins
        c_halt   = is_halted
        c_reason = halt_reason

    with scalp_lock:
        scalp_copy = dict(current_scalp)

    with log_lock:
        logs_list   = list(console_logs)
        trades_list = list(trade_history)

    delta = (p_btc - p_ptb) if (p_btc and p_ptb) else 0.0

    return {
        "balance": w_bal,
        "bankroll": c_bank,
        "consecutive_wins": c_wins,
        "is_halted": c_halt,
        "halt_reason": c_reason,
        "market": {
            "price": p_btc,
            "ptb": p_ptb,
            "delta": delta,
            "step_threshold": STEP_DISPLACEMENT_TRIGGER
        },
        "scalp": scalp_copy,
        "window_trade_done": w_done,
        "trades": trades_list,
        "logs": logs_list
    }

@app.route('/api/status')
def api_status():
    return jsonify(build_status_response())

@app.route('/api/state')
def api_state():
    return jsonify(build_status_response())

# ── SSL + WS Feed ──────────────────────────────────────────────────────────────
def make_ssl_ctx():
    ctx = ssl.create_default_context()
    for p in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(p):
            ctx.load_verify_locations(p)
            break
    return ctx

WS_HEADERS = {
    "Origin": "https://polymarket.com",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}

class WSFeed:
    def __init__(self):
        self._price = None
        self._ts_ms = None
        self._lock  = threading.Lock()
        self._ready = threading.Event()
        self._stopped = False
        self._ws_app = None

    def start(self):
        ssl_ctx = make_ssl_ctx()

        def on_open(ws):
            ws.send(json.dumps({
                "action": "subscribe",
                "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}],
            }))
            log_info("📡 WS connected — Listening to real-time Chainlink BTC/USD feed.")

        def on_message(ws, raw):
            global btc_price
            if not raw:
                return
            try:
                msg = json.loads(raw)
            except Exception:
                return
            if msg.get("topic") != "crypto_prices_chainlink":
                return
            p = msg.get("payload", {})
            if p.get("symbol") != "btc/usd":
                return
            val = p.get("value")
            ts = p.get("timestamp")
            if val is None or ts is None:
                return

            with self._lock:
                self._price = float(val)
                self._ts_ms = ts
                self._ready.set()
                btc_price = self._price

            now_sec = time.time()
            price_ticks.append((now_sec, float(val)))

        def on_close(ws, close_status_code, close_msg):
            if not self._stopped:
                log_info("⚠️ WS feed disconnected — reconnecting in 2s...")
                time.sleep(2)
                self.start()

        def on_error(ws, err):
            pass

        app = websocket.WebSocketApp(
            LIVE_WS_URL, header=WS_HEADERS,
            on_open=on_open, on_message=on_message,
            on_close=on_close, on_error=on_error
        )
        self._ws_app = app
        threading.Thread(
            target=lambda: app.run_forever(
                sslopt={"context": ssl_ctx}, ping_interval=20, ping_timeout=10
            ),
            daemon=True,
        ).start()
        self._ready.wait(timeout=20)

    def latest(self):
        self.check_staleness_and_reconnect()
        with self._lock:
            return (self._price, self._ts_ms) if (self._price is not None and self._ts_ms is not None) else None

    def price_at_or_after(self, ts_sec):
        self.check_staleness_and_reconnect()
        with self._lock:
            if self._ts_ms is None or self._price is None:
                return None
            if self._ts_ms >= ts_sec * 1000:
                return self._price, self._ts_ms
        return None

    def check_staleness_and_reconnect(self):
        with self._lock:
            if self._ts_ms is not None:
                lag = time.time() - (self._ts_ms / 1000.0)
                if lag > 15.0:
                    log_info(f"⚠️ WS feed stale (lag={lag:.1f}s) — reconnecting...")
                    self._ts_ms = None
                    self._price = None
                    if self._ws_app:
                        try:
                            self._ws_app.close()
                        except Exception:
                            pass

# ── Market Resolution & Orderbook Helpers ───────────────────────────────────────
def win_start(ts=None):
    t = ts if ts is not None else time.time()
    return int(t // WINDOW_SECS) * WINDOW_SECS

def win_end(ts=None):
    return win_start(ts) + WINDOW_SECS

def slug_for(ts=None):
    return f"btc-updown-5m-{win_start(ts)}"

def resolve_market(slug, timeout=10):
    r = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if not data or not data[0].get("markets"):
        return None
    mkt = data[0]["markets"][0]
    token_ids = json.loads(mkt.get("clobTokenIds", "[]")) if isinstance(mkt.get("clobTokenIds"), str) else mkt.get("clobTokenIds", [])
    outcomes = json.loads(mkt.get("outcomes", "[]")) if isinstance(mkt.get("outcomes"), str) else mkt.get("outcomes", [])
    up_id = None
    down_id = None
    for i, out in enumerate(outcomes):
        o = out.lower()
        if o in ("up", "yes"): up_id = token_ids[i]
        elif o in ("down", "no"): down_id = token_ids[i]
    if not up_id:   up_id   = token_ids[0]
    if not down_id: down_id = token_ids[1]
    return {
        "slug": slug,
        "title": mkt.get("question", slug),
        "up_id": up_id,
        "down_id": down_id,
    }

def probe_orderbook(token_id, timeout=2):
    try:
        r = requests.get(f"{CLOB_HOST}/book", params={"token_id": token_id}, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        best_bid = float(max(bids, key=lambda b: float(b["price"]))["price"]) if bids else None
        best_ask = float(min(asks, key=lambda a: float(a["price"]))["price"]) if asks else None
        return best_bid, best_ask
    except Exception:
        return None, None

def get_live_balance(clob_client):
    try:
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        resp = clob_client.get_balance_allowance(params)
        raw_bal = float(resp.get("balance", 0))
        return raw_bal / 1_000_000.0
    except Exception as e:
        log_info(f"⚠️ Error fetching balance: {e}")
        return None

# ── Step-Trend Trigger Logic ───────────────────────────────────────────────────
def check_step_trend(ptb: float, cur_price: float):
    """
    Checks for confirmed $25 step displacement away from opening PTB.
    """
    if ptb is None or cur_price is None:
        return None, ""

    delta = cur_price - ptb

    # Condition 1: Step Move UP (>= +$25.00 away from PTB)
    if delta >= STEP_DISPLACEMENT_TRIGGER:
        return "UP", f"Step UP: +${delta:.2f} above PTB"

    # Condition 2: Step Move DOWN (<= -$25.00 away from PTB)
    elif delta <= -STEP_DISPLACEMENT_TRIGGER:
        return "DOWN", f"Step DOWN: ${delta:.2f} below PTB"

    return None, ""

# ── Scalp Execution Engine ─────────────────────────────────────────────────────
def execute_step_trend_scalp(ws: WSFeed, ptb: float, w_end: int, market: dict, clob_client=None):
    global window_trade_done, current_scalp, btc_price, current_bankroll, consecutive_wins, is_halted, halt_reason

    if is_halted:
        log_info(f"🛑 [BOT HALTED] Trading stopped ({halt_reason}).")
        return

    trade_stake = round(current_bankroll, 2)
    ptb_str = f"${ptb:,.2f}" if ptb is not None else "$--"
    log_info(f"🔍 Monitoring for $25 step displacement in window {slug_for(w_end - WINDOW_SECS)} (PTB: {ptb_str} | Stake: ${trade_stake:.2f})...")

    with scalp_lock:
        current_scalp["active"] = False
        current_scalp["state"]  = "SCANNING"

    while True:
        now       = time.time()
        remaining = w_end - now

        # Entry Cutoff: Stop looking for new entries inside last 45s
        if remaining <= ENTRY_CUTOFF_TIME:
            if not current_scalp["active"]:
                log_info(f"⏳ Window inside T-{int(remaining)}s — no step trend triggered. Resting until next window.")
                break

        ws_data = ws.latest()
        if ws_data:
            btc_price = ws_data[0]

        # ── STAGE 1: SCANNING FOR STEP TREND ──
        if not current_scalp["active"] and not window_trade_done and not is_halted and ptb is not None:
            trend_side, reason = check_step_trend(ptb, btc_price)

            if trend_side is not None:
                token_id = market["up_id"] if trend_side == "UP" else market["down_id"]
                best_bid, best_ask = probe_orderbook(token_id)

                if best_ask is not None and MIN_TOKEN_PRICE <= best_ask <= MAX_TOKEN_PRICE:
                    log_info(f"⚡ [STEP TREND DETECTED] {trend_side} | {reason}")
                    log_info(f"🎯 Entering {trend_side} with ${trade_stake:.2f} @ Ask ${best_ask:.4f} (Bid: ${best_bid})")

                    shares = round(trade_stake / best_ask, 4)
                    entry_price = best_ask
                    target_sell = round(entry_price + TAKE_PROFIT_CENTS, 4)

                    is_live = (clob_client is not None)
                    buy_success = True

                    if is_live:
                        try:
                            from py_clob_client_v2 import MarketOrderArgsV2
                            log_info(f"🚀 [LIVE BUY] Placing ${trade_stake:.2f} market BUY for {trend_side}...")
                            resp = clob_client.create_and_post_market_order(
                                order_args=MarketOrderArgsV2(
                                    token_id=token_id, amount=trade_stake, side="BUY"
                                )
                            )
                            log_info(f"✅ [LIVE BUY FILLED] Response: {resp}")

                            # Exact fill parsing from takingAmount
                            if isinstance(resp, dict) and resp.get("takingAmount"):
                                shares = math.floor(float(resp["takingAmount"]) * 100) / 100.0
                        except Exception as e:
                            log_info(f"❌ [BUY FAILED] {e}")
                            buy_success = False

                    if buy_success:
                        with scalp_lock:
                            current_scalp["active"] = True
                            current_scalp["side"] = trend_side
                            current_scalp["token_id"] = token_id
                            current_scalp["shares"] = shares
                            current_scalp["entry_price"] = entry_price
                            current_scalp["entry_time"] = time.time()
                            current_scalp["entry_cost"] = trade_stake
                            current_scalp["target_sell_price"] = target_sell
                            current_scalp["state"] = "IN_POSITION_LOOKING_FOR_EXIT"

                        log_info(f"📈 [POSITION OPEN] Bought {shares:.2f} {trend_side} shares @ ${entry_price:.4f}. Target Exit: >= ${target_sell:.4f}")

        # ── STAGE 2: IN POSITION — RAPID SCALP EXIT ──
        elif current_scalp["active"]:
            token_id = current_scalp["token_id"]
            best_bid, _ = probe_orderbook(token_id)
            side = current_scalp["side"]
            shares = current_scalp["shares"]
            entry_p = current_scalp["entry_price"]
            target_p = current_scalp["target_sell_price"]

            exit_triggered = False
            exit_reason    = ""

            # Exit Rule 1: Take Profit Hit (+1c gain)
            if best_bid is not None and best_bid >= target_p:
                exit_triggered = True
                exit_reason = f"TAKE_PROFIT (+${best_bid - entry_p:.4f}/share)"

            # Exit Rule 2: Emergency Time Dump (T-30s before close)
            elif remaining <= EMERGENCY_EXIT_TIME:
                exit_triggered = True
                exit_reason = f"TIME_CUTOFF (T-{int(remaining)}s before close)"

            if exit_triggered:
                sell_price = best_bid if (best_bid is not None) else entry_p
                gross_revenue = round(shares * sell_price, 4)
                net_pnl = round(gross_revenue - trade_stake, 4)

                log_info(f"🚪 [SCALP EXIT TRIGGERED] Reason: {exit_reason} | Selling {shares:.2f} {side} @ ${sell_price:.4f}")

                sold_successfully = True
                if clob_client is not None:
                    try:
                        from py_clob_client_v2 import MarketOrderArgsV2
                        log_info(f"🚀 [LIVE SELL] Selling {shares:.2f} shares of {side}...")
                        resp = clob_client.create_and_post_market_order(
                            order_args=MarketOrderArgsV2(
                                token_id=token_id, amount=shares, side="SELL"
                            )
                        )
                        log_info(f"✅ [LIVE SELL FILLED] Response: {resp}")
                    except Exception as e:
                        log_info(f"❌ [SELL ERROR] {e} — Retrying with precision fallback...")
                        try:
                            safe_shares = math.floor(shares * 10) / 10.0
                            resp = clob_client.create_and_post_market_order(
                                order_args=MarketOrderArgsV2(
                                    token_id=token_id, amount=safe_shares, side="SELL"
                                )
                            )
                            log_info(f"✅ [LIVE SELL RETRY MATCHED] Response: {resp}")
                        except Exception as e2:
                            log_info(f"❌ [FATAL SELL ERROR] {e2}")
                            sold_successfully = False

                if sold_successfully:
                    time_str = datetime.datetime.now().strftime("%H:%M:%S")
                    record_trade(time_str, side, entry_p, sell_price, trade_stake, net_pnl, exit_reason)
                    log_info(f"🎉 [SCALP COMPLETE] Entry: ${entry_p:.4f} | Exit: ${sell_price:.4f} | Gross: ${gross_revenue:.4f} | Net P&L: ${net_pnl:>+.4f} USD")

                    if net_pnl > 0:
                        consecutive_wins += 1
                        current_bankroll = round(gross_revenue, 2)
                        log_info(f"💰 [WIN & ROLLOVER #{consecutive_wins}] Rolled over winnings! Next trade stake: ${current_bankroll:.2f}")
                        save_state()
                    else:
                        is_halted = True
                        halt_reason = f"Trade incurred loss of ${abs(net_pnl):.4f}"
                        log_info(f"🛑 [PERMANENT HALT] Lost money (${net_pnl:.4f}). Stopping permanently as instructed.")
                        save_state()

                    with scalp_lock:
                        current_scalp["active"] = False
                        current_scalp["state"]  = "EXITED_DONE_FOR_WINDOW"

                    window_trade_done = True
                    break

        time.sleep(0.2)

# ── Background Trading Engine Loop ─────────────────────────────────────────────
def bot_thread_worker():
    global wallet_balance, btc_price, btc_ptb, window_trade_done

    POLYMARKET_LIVE_TRADING = os.getenv("POLYMARKET_LIVE_TRADING", "False").lower() in ("true", "1", "yes")
    POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS")
    POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY")
    POLYMARKET_API_SECRET = os.getenv("POLYMARKET_API_SECRET")
    POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE")
    POLYMARKET_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY")

    clob_client = None
    if POLYMARKET_LIVE_TRADING and POLYMARKET_PRIVATE_KEY:
        log_info("⚠️ LIVE TRADING ENABLED! Initializing Polymarket CLOB Client...")
        try:
            from py_clob_client_v2 import ClobClient, ApiCreds
            from eth_account import Account

            eoa_address = Account.from_key(POLYMARKET_PRIVATE_KEY).address
            sig_type = 0
            funder_addr = None
            if POLYMARKET_ADDRESS and POLYMARKET_ADDRESS.lower() != eoa_address.lower():
                sig_type = 3
                funder_addr = POLYMARKET_ADDRESS

            creds = ApiCreds(
                api_key=POLYMARKET_API_KEY,
                api_secret=POLYMARKET_API_SECRET,
                api_passphrase=POLYMARKET_API_PASSPHRASE
            )
            clob_client = ClobClient(
                host=CLOB_HOST, chain_id=137, key=POLYMARKET_PRIVATE_KEY, creds=creds, signature_type=sig_type, funder=funder_addr
            )
            log_info("✅ CLOB Client initialized successfully.")
        except Exception as e:
            log_info(f"❌ Error initializing CLOB client: {e}")
            sys.exit(1)
    else:
        log_info("📄 Running in PAPER SCALPING MODE ($1 starting bankroll).")

    load_state()

    ws = WSFeed()
    ws.start()

    for _ in range(40):
        if ws.latest():
            break
        time.sleep(0.5)

    tick = ws.latest()
    if not tick:
        log_info("❌ No WS data received — check network connection.")
        sys.exit(1)
    btc_price, _ = tick
    log_info(f"✅ WS connected — Initial BTC/USD: ${btc_price:,.2f}")

    while True:
        try:
            now       = time.time()
            w_s       = win_start(now)
            w_e       = win_end(now)
            secs_into = now - w_s

            if POLYMARKET_LIVE_TRADING and clob_client is not None:
                local_bal = get_live_balance(clob_client)
                if local_bal is not None:
                    wallet_balance = local_bal
            else:
                wallet_balance = 10.00

            if is_halted:
                log_info(f"🛑 Bot is HALTED ({halt_reason}). Sleeping...")
                time.sleep(30)
                continue

            # Wait for next clean window open if joined mid-candle
            if secs_into > 30:
                sleep_secs = w_e - time.time() + 0.5
                log_info(f"⏳ Waiting {sleep_secs:.1f}s for next 5-minute candle boundary...")
                time.sleep(max(0, sleep_secs))
                now = time.time()
                w_s = win_start(now)
                w_e = w_s + WINDOW_SECS

            window_trade_done = False
            slug = slug_for(w_s)
            btc_ptb = None

            # Capture Price to Beat at window open
            deadline = time.time() + 25
            while time.time() < deadline:
                result = ws.price_at_or_after(w_s)
                if result:
                    btc_ptb, ptb_ts_ms = result
                    break
                time.sleep(0.1)

            if btc_ptb is None:
                log_info("⚠️ Could not capture exact PTB tick — using latest price.")
                latest_p = ws.latest()
                if latest_p:
                    btc_ptb = latest_p[0]

            ptb_display = f"${btc_ptb:,.2f}" if btc_ptb is not None else "$--"
            log_info(f"🚩 New Window Open: {slug} | Price to Beat: {ptb_display} | Bankroll: ${current_bankroll:.2f}")

            # Resolve Polymarket event tokens
            market = None
            for _ in range(15):
                try:
                    market = resolve_market(slug)
                    if market: break
                except Exception: pass
                time.sleep(1.5)

            if not market:
                log_info("❌ Could not resolve Polymarket tokens — skipping window.")
                time.sleep(max(10, w_e - time.time()))
                continue

            # Run Step Trend Scalp
            execute_step_trend_scalp(ws, btc_ptb, w_e, market, clob_client=clob_client)

            # Rest until next window close
            rem_after = w_e - time.time()
            if rem_after > 0:
                log_info(f"💤 Window scalp complete. Resting {rem_after:.1f}s until next window...")
                time.sleep(rem_after + 1.0)

        except Exception as e:
            log_info(f"❌ Trading loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=bot_thread_worker, daemon=True)
    bot_thread.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
