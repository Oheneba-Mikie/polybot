#!/usr/bin/env python3
"""
app.py — $1 In-and-Out Sudden Trend Scalper Bot + Live Web Dashboard for Railway

Strategy:
1. Starting Bankroll: Exactly $1.00.
2. Market Order on Polymarket: Buys $1.00 worth of shares (not a fixed share count).
3. Sudden Trend Detection: Real-time velocity tracker (3s & 5s price rate-of-change + PTB displacement).
4. In-and-Out Scalp: Buys on breakout, immediately monitors for exit (+1c gain). Never holds across window close (emergency market-sell at T-30s).
5. Rollover & Halt Rules:
   - IF WIN: Rolls over total balance ($1.00 + winnings) into the next window.
   - IF LOSS: PERMANENT HALT. Never goes in again if that $1 is lost.
"""

import json
import os
import ssl
import sys
import time
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

# Trend Detection Parameters
VELOCITY_3S_TRIGGER  = 25.0     # $25 move in 3 seconds
VELOCITY_5S_TRIGGER  = 35.0     # $35 move in 5 seconds
MIN_PTB_DISPLACEMENT = 30.0     # Must be at least $30 away from Price to Beat
MIN_TOKEN_PRICE      = 0.45     # Don't buy dead/decayed tokens
MAX_TOKEN_PRICE      = 0.75     # Don't buy over-saturated tokens (leave room to scalp)

# Scalp Exit Parameters
TAKE_PROFIT_CENTS    = 0.01     # Exit immediately once price is +1 cent or higher (even for a cent!)
EMERGENCY_EXIT_TIME  = 30       # T-30s: Emergency sell before window closes. NEVER hold across expiry.
REVERSAL_SL_USD      = 25.0     # Bailout if BTC snaps back across PTB by >$25

STATE_FILE = "scalper_state.json"

# ── Global State ────────────────────────────────────────────────────────────────
current_bankroll  = 1.00        # Starts with $1.00, rolls over on win
consecutive_wins  = 0
is_halted         = False       # If we lose, halted forever
halt_reason       = ""

wallet_balance    = 0.00
btc_price         = 0.00
btc_ptb           = 0.00
btc_velocity_3s   = 0.00
btc_velocity_5s   = 0.00
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
price_ticks   = deque(maxlen=300) # (timestamp, price)

log_lock   = threading.Lock()
state_lock = threading.Lock()
scalp_lock = threading.Lock()

# ── State Persistence Helpers ───────────────────────────────────────────────────
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

# ── Logging & Analytics ─────────────────────────────────────────────────────────
def log_info(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    sys.stdout.flush()
    with log_lock:
        console_logs.append(formatted)

def record_trade(time_str, side, entry_p, exit_p, stake, pnl, reason):
    with log_lock:
        trade_history.appendleft({
            "time": time_str,
            "side": side,
            "entry_price": entry_p,
            "exit_price": exit_p,
            "stake": stake,
            "pnl": pnl,
            "outcome": "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "EVEN"),
            "reason": reason
        })

# ── Web Server Setup ────────────────────────────────────────────────────────────
import logging
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=template_dir)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

@app.route('/')
def home():
    return render_template('dashboard.html')

@app.route('/api/status')
def api_status():
    with state_lock:
        w_bal    = wallet_balance
        p_btc    = btc_price
        p_ptb    = btc_ptb
        v_3s     = btc_velocity_3s
        v_5s     = btc_velocity_5s
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

    return jsonify({
        "balance": w_bal,
        "bankroll": c_bank,
        "consecutive_wins": c_wins,
        "is_halted": c_halt,
        "halt_reason": c_reason,
        "market": {
            "price": p_btc,
            "ptb": p_ptb,
            "velocity_3s": v_3s,
            "velocity_5s": v_5s
        },
        "scalp": scalp_copy,
        "window_trade_done": w_done,
        "trades": trades_list,
        "logs": logs_list
    })

# ── SSL + WS headers ────────────────────────────────────────────────────────────
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

# ── Time helpers ─────────────────────────────────────────────────────────────────
def win_start(ts=None):
    t = ts if ts is not None else time.time()
    return int(t // WINDOW_SECS) * WINDOW_SECS

def win_end(ts=None):
    return win_start(ts) + WINDOW_SECS

def slug_for(ts=None):
    return f"btc-updown-5m-{win_start(ts)}"

def fmt(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")

# ── WS Feed & Velocity Tracking ─────────────────────────────────────────────────
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

        def on_message(ws, raw):
            global btc_price, btc_velocity_3s, btc_velocity_5s
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

            # Compute real-time velocity
            t3 = now_sec - 3.0
            t5 = now_sec - 5.0
            p3 = None
            p5 = None
            for t_time, t_val in price_ticks:
                if p5 is None and t_time >= t5:
                    p5 = t_val
                if p3 is None and t_time >= t3:
                    p3 = t_val

            if p3 is not None:
                btc_velocity_3s = float(val) - p3
            if p5 is not None:
                btc_velocity_5s = float(val) - p5

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

# ── Polymarket Market & Book Queries ─────────────────────────────────────────────
def resolve_market(slug, timeout=10):
    r = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=timeout)
    r.raise_for_status()
    events = r.json()
    if not events:
        return None
    mkt = events[0]["markets"][0]
    token_ids = json.loads(mkt.get("clobTokenIds") or "[]")
    outcomes  = [str(o).lower() for o in json.loads(mkt.get("outcomes") or "[]")]
    up_id = down_id = None
    for i, o in enumerate(outcomes):
        if o in ("up", "yes"):    up_id   = token_ids[i]
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
    """Returns (best_bid, best_ask) for a token."""
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

# ── Trend Detection Engine ───────────────────────────────────────────────────────
def check_sudden_trend(ptb: float, cur_price: float, v3: float, v5: float):
    """
    Returns ('UP'|'DOWN'|None, reason) if a 1000% definitive sudden trend burst occurred.
    """
    if ptb is None or cur_price is None:
        return None, ""

    delta_ptb = cur_price - ptb

    # Condition 1: Fast Upward Spike
    if (v3 >= VELOCITY_3S_TRIGGER or v5 >= VELOCITY_5S_TRIGGER) and delta_ptb >= MIN_PTB_DISPLACEMENT:
        return "UP", f"Burst UP: +${v3:.1f}/3s (+${v5:.1f}/5s), PTB delta: +${delta_ptb:.1f}"

    # Condition 2: Fast Downward Spike
    if (v3 <= -VELOCITY_3S_TRIGGER or v5 <= -VELOCITY_5S_TRIGGER) and delta_ptb <= -MIN_PTB_DISPLACEMENT:
        return "DOWN", f"Burst DOWN: ${v3:.1f}/3s (${v5:.1f}/5s), PTB delta: ${delta_ptb:.1f}"

    return None, ""

# ── Scalp Execution Engine ───────────────────────────────────────────────────────
def execute_trend_scalp(ws: WSFeed, ptb: float, w_end: int, market: dict, clob_client=None):
    """
    Monitors 5-minute candle in real time:
    1. Checks if halted.
    2. Awaits sudden trend boom.
    3. Places market BUY order with current bankroll (starts $1.00).
    4. Exits immediately on +1c profit or T-30s cutoff.
    5. Rollover: if win -> roll over total balance; if loss -> HALT PERMANENTLY.
    """
    global window_trade_done, current_scalp, btc_price, current_bankroll, consecutive_wins, is_halted, halt_reason

    if is_halted:
        log_info(f"🛑 [BOT HALTED] Trading stopped permanently ({halt_reason}). No orders will be placed.")
        return

    trade_stake = round(current_bankroll, 2)
    log_info(f"🔍 Monitoring for sudden trend bursts in window {slug_for(w_end - WINDOW_SECS)} (PTB: ${ptb:,.2f} | Stake: ${trade_stake:.2f})...")
    
    # Reset scalp state for new window
    with scalp_lock:
        current_scalp["active"] = False
        current_scalp["state"]  = "SCANNING"

    while True:
        now       = time.time()
        remaining = w_end - now

        # Window cutoff: Stop trading if too close to end (no new entries inside T-45s)
        if remaining <= 45:
            if not current_scalp["active"]:
                log_info(f"⏳ Window inside T-{int(remaining)}s — no trend fired this window. Rolling over.")
                break

        ws_data = ws.latest()
        if ws_data:
            btc_price = ws_data[0]

        # ── STAGE 1: SCANNING FOR SUDDEN TREND ──
        if not current_scalp["active"] and not window_trade_done and not is_halted:
            trend_side, reason = check_sudden_trend(ptb, btc_price, btc_velocity_3s, btc_velocity_5s)
            
            if trend_side is not None:
                token_id = market["up_id"] if trend_side == "UP" else market["down_id"]
                best_bid, best_ask = probe_orderbook(token_id)

                if best_ask is not None and MIN_TOKEN_PRICE <= best_ask <= MAX_TOKEN_PRICE:
                    log_info(f"⚡ [SUDDEN TREND DETECTED] {trend_side} | {reason}")
                    log_info(f"🎯 Placing trade on {trend_side} with ${trade_stake:.2f} @ Ask ${best_ask:.4f} (Bid: ${best_bid})")

                    shares = round(trade_stake / best_ask, 4)
                    entry_price = best_ask
                    target_sell = round(entry_price + TAKE_PROFIT_CENTS, 4)

                    # Execute Buy Order on Polymarket
                    is_live = (clob_client is not None)
                    buy_success = True
                    if is_live:
                        try:
                            from py_clob_client_v2 import MarketOrderArgsV2
                            log_info(f"🚀 [LIVE BUY] Placing ${trade_stake:.2f} market BUY order for {trend_side}...")
                            resp = clob_client.create_and_post_market_order(
                                order_args=MarketOrderArgsV2(
                                    token_id=token_id, amount=trade_stake, side="BUY"
                                )
                            )
                            log_info(f"✅ [LIVE BUY FILLED] Response: {resp}")
                        except Exception as e:
                            log_info(f"❌ [BUY FAILED] Order error: {e}")
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
                        
                        log_info(f"📈 [POSITION OPEN] Bought {shares:.2f} {trend_side} shares for ${trade_stake:.2f} @ ${entry_price:.4f}. Target Exit: >= ${target_sell:.4f}")

        # ── STAGE 2: IN POSITION — MONITOR FOR IMMEDIATE EXIT ──
        elif current_scalp["active"]:
            token_id = current_scalp["token_id"]
            best_bid, best_ask = probe_orderbook(token_id)
            side = current_scalp["side"]
            shares = current_scalp["shares"]
            entry_p = current_scalp["entry_price"]
            target_p = current_scalp["target_sell_price"]

            exit_triggered = False
            exit_reason    = ""

            # Exit Rule 1: Take Profit Hit (Even for 1 cent gain!)
            if best_bid is not None and best_bid >= target_p:
                exit_triggered = True
                exit_reason = f"TAKE_PROFIT (+${best_bid - entry_p:.4f}/share)"

            # Exit Rule 2: Emergency Time Exit (T-30s: NEVER hold to expiry)
            elif remaining <= EMERGENCY_EXIT_TIME:
                exit_triggered = True
                exit_reason = f"TIME_CUTOFF (T-{int(remaining)}s before close)"

            # Exit Rule 3: Sharp Reversal Cutoff (Protect Capital)
            elif ptb is not None:
                delta = btc_price - ptb
                if (side == "UP" and delta < -REVERSAL_SL_USD) or (side == "DOWN" and delta > REVERSAL_SL_USD):
                    exit_triggered = True
                    exit_reason = f"REVERSAL_CUTOFF (BTC flipped delta ${delta:.1f})"

            if exit_triggered:
                sell_price = best_bid if (best_bid is not None) else entry_p
                gross_revenue = round(shares * sell_price, 4)
                net_pnl = round(gross_revenue - trade_stake, 4)

                log_info(f"🚪 [SCALP EXIT TRIGGERED] Reason: {exit_reason} | Selling {shares:.2f} {side} @ ${sell_price:.4f}")

                # Execute Sell Order on Polymarket
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
                        log_info(f"❌ [SELL ERROR] {e}")

                time_str = datetime.datetime.now().strftime("%H:%M:%S")
                record_trade(time_str, side, entry_p, sell_price, trade_stake, net_pnl, exit_reason)
                
                log_info(f"🎉 [SCALP COMPLETE] Entry: ${entry_p:.4f} | Exit: ${sell_price:.4f} | Gross: ${gross_revenue:.4f} | Net P&L: ${net_pnl:>+.4f} USD")

                # ── ROLLOVER & HALT MANAGEMENT ──
                if net_pnl > 0:
                    consecutive_wins += 1
                    current_bankroll = round(gross_revenue, 2)
                    log_info(f"💰 [WIN & ROLLOVER #{consecutive_wins}] Rolled over winnings! Next window trade size: ${current_bankroll:.2f}")
                    save_state()
                else:
                    is_halted = True
                    halt_reason = f"Trade incurred a loss of ${abs(net_pnl):.4f}"
                    log_info(f"🛑 [PERMANENT HALT] Lost money (${net_pnl:.4f}). As instructed, the initial $1 is gone and the bot will NEVER enter again.")
                    save_state()

                with scalp_lock:
                    current_scalp["active"] = False
                    current_scalp["state"]  = "EXITED_DONE_FOR_WINDOW"

                window_trade_done = True
                break

        time.sleep(0.2)

# ── Core Background Trading Loop ────────────────────────────────────────────────
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
        log_info("📄 Running in DRY RUN / PAPER SCALPING MODE ($1 starting bankroll).")

    load_state()

    ws = WSFeed()
    ws.start()

    for _ in range(40):
        if ws.latest():
            break
        time.sleep(0.5)
    tick = ws.latest()
    if not tick:
        log_info("❌ No WS data — check network connection.")
        sys.exit(1)
    btc_price, _ = tick
    log_info(f"✅ WS connected — Initial BTC/USD: ${btc_price:,.2f}")

    while True:
        try:
            now       = time.time()
            w_s       = win_start(now)
            w_e       = win_end(now)
            secs_into = now - w_s
            remaining = w_e - now

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

            # If we joined mid-window past 30 seconds, wait for the next clean window open
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

            log_info(f"🚩 New Window Open: {slug} | Price to Beat: ${btc_ptb:,.2f} | Bankroll: ${current_bankroll:.2f}")

            # Resolve Polymarket event tokens
            market = None
            for _ in range(15):
                try:
                    market = resolve_market(slug)
                    if market:
                        break
                except Exception:
                    pass
                time.sleep(1.5)

            if not market:
                log_info("❌ Could not resolve Polymarket tokens — skipping window.")
                time.sleep(max(10, w_e - time.time()))
                continue

            # Run In-and-Out Trend Scalper for this window
            execute_trend_scalp(ws, btc_ptb, w_e, market, clob_client=clob_client)

            # Rest until next window close
            rem_after = w_e - time.time()
            if rem_after > 0:
                log_info(f"💤 Window scalp complete. Resting {rem_after:.1f}s until next window...")
                time.sleep(rem_after + 1.0)

        except Exception as e:
            log_info(f"❌ Error in trading loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # Start trading engine thread
    bot_thread = threading.Thread(target=bot_thread_worker, daemon=True)
    bot_thread.start()

    # Start Flask Web Dashboard on Railway PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
