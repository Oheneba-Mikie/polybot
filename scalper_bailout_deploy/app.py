#!/usr/bin/env python3
"""
app.py — In-and-Out Sudden Trend Scalper Bot + Live Web Dashboard for Railway

Strategy:
1. Starting Bankroll: Exactly $1.00 (compounds on every win).
2. Market Order on Polymarket: Buys bankroll worth of shares.
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
import math
import logging
import datetime
import threading
from collections import deque
from flask import Flask, jsonify, render_template_string
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
MIN_PTB_DISPLACEMENT = 25.0     # Must be at least $25 away from Price to Beat
MIN_TOKEN_PRICE      = 0.45     # Don't buy dead/decayed tokens
MAX_TOKEN_PRICE      = 0.80     # Don't buy over-saturated tokens (leave room to scalp)

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

trade_history = deque(maxlen=50)
console_logs  = deque(maxlen=100)
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
app = Flask(__name__)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

def build_status_response():
    with state_lock:
        w_bal    = wallet_balance
        p_btc    = btc_price
        p_ptb    = btc_ptb
        v3       = btc_velocity_3s
        v5       = btc_velocity_5s
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
            "v3": v3,
            "v5": v5,
            "velocity_trigger": VELOCITY_3S_TRIGGER
        },
        "scalp": scalp_copy,
        "window_trade_done": w_done,
        "trades": trades_list,
        "logs": logs_list
    }

@app.route('/')
def home():
    st = build_status_response()
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>⚡ In-and-Out Sudden Trend Scalper</title>
        <meta http-equiv="refresh" content="2">
        <style>
            body {{ background: #080c14; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; }}
            .card {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 12px; padding: 25px; max-width: 1000px; margin: 0 auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); }}
            h1 {{ color: #10b981; margin-top: 0; display: flex; align-items: center; justify-content: space-between; font-size: 22px; }}
            .badge {{ background: #10b981; color: #000; padding: 5px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
            .stats {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin: 15px 0; }}
            .stat-box {{ background: #1e293b; padding: 12px; border-radius: 8px; text-align: center; border: 1px solid #334155; }}
            .stat-label {{ font-size: 12px; color: #94a3b8; margin-bottom: 4px; }}
            .stat-val {{ font-size: 20px; font-weight: bold; color: #10b981; }}
            .candle-bar {{ background: #1e293b; padding: 10px 15px; border-radius: 6px; font-weight: 500; margin-bottom: 12px; color: #38bdf8; display: flex; justify-content: space-between; font-size: 13px; }}
            .log-box {{ background: #020617; border-radius: 8px; padding: 12px; height: 300px; overflow-y: auto; font-family: monospace; font-size: 12px; color: #a7f3d0; border: 1px solid #1e293b; }}
            .trade-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 12px; }}
            .trade-table th, .trade-table td {{ padding: 8px; text-align: left; border-bottom: 1px solid #1e293b; }}
            .trade-table th {{ background: #1e293b; color: #94a3b8; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>
                <span>⚡ In-and-Out Sudden Trend Scalper</span>
                <span class="badge">ACTIVE (Rollover Compounding)</span>
            </h1>
            <div class="candle-bar">
                <span>BTC Price: ${(st['market']['price'] or 0):,.2f} | PTB Strike: ${(st['market']['ptb'] or 0):,.2f}</span>
                <span>Delta: ${(st['market']['delta'] or 0):+.2f} | Velocity 3s: ${(st['market']['v3'] or 0):+.1f}</span>
            </div>
            <div class="stats">
                <div class="stat-box"><div class="stat-label">Consecutive Wins</div><div class="stat-val">{st['consecutive_wins']}</div></div>
                <div class="stat-box"><div class="stat-label">Active Bankroll</div><div class="stat-val">${st['bankroll']:.2f}</div></div>
                <div class="stat-box"><div class="stat-label">Wallet Balance</div><div class="stat-val">${(st['balance'] or 0):.2f}</div></div>
                <div class="stat-box"><div class="stat-label">Scalp Status</div><div class="stat-val" style="font-size:14px; color:#38bdf8;">{st['scalp']['state']}</div></div>
                <div class="stat-box"><div class="stat-label">Total Trades</div><div class="stat-val">{len(st['trades'])}</div></div>
            </div>
            <h3>📜 Live Millisecond Logs</h3>
            <div class="log-box">
                {"<br>".join(reversed(st['logs']))}
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/api/status')
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
    "User-Agent": "Mozilla/5.0",
}

class WSFeed:
    def __init__(self):
        self._price = None
        self._ts_ms = None
        self._lock  = threading.Lock()
        self._ready = threading.Event()
        self._stopped = False

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

            # Record price tick for velocity calculation
            now = time.time()
            with state_lock:
                price_ticks.append((now, float(val)))
                update_velocities(now)

        def on_error(ws, err):
            log_info(f"⚠️ WS error: {err}")

        def on_close(ws, close_status, close_msg):
            log_info("⚠️ WS disconnected. Reconnecting in 2s...")
            time.sleep(2)
            if not self._stopped:
                self.start()

        def runner():
            app_ws = websocket.WebSocketApp(
                LIVE_WS_URL,
                header=WS_HEADERS,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )
            app_ws.run_forever(sslopt={"context": ssl_ctx})

        threading.Thread(target=runner, daemon=True).start()

    def latest(self):
        with self._lock:
            return self._price, self._ts_ms

def update_velocities(now: float):
    global btc_velocity_3s, btc_velocity_5s
    if len(price_ticks) < 2:
        return

    cur_p = price_ticks[-1][1]
    p_3s = None
    p_5s = None

    for t, p in reversed(price_ticks):
        age = now - t
        if p_3s is None and age >= 3.0:
            p_3s = p
        if p_5s is None and age >= 5.0:
            p_5s = p
            break

    if p_3s is not None:
        btc_velocity_3s = cur_p - p_3s
    if p_5s is not None:
        btc_velocity_5s = cur_p - p_5s

def win_start(ts=None):
    t = ts if ts is not None else time.time()
    return int(t // WINDOW_SECS) * WINDOW_SECS

def win_end(ts=None):
    return win_start(ts) + WINDOW_SECS

def slug_for(start_ts):
    return f"btc-updown-5m-{start_ts}"

def fetch_ptb_strike(ws: WSFeed, w_start: int, timeout=15):
    log_info(f"⏳ Waiting for exact candle open timestamp {w_start} to lock PTB...")
    while time.time() < w_start:
        time.sleep(0.01)

    t0 = time.time()
    while time.time() - t0 < timeout:
        ws_data = ws.latest()
        if ws_data and ws_data[0] is not None:
            ptb = ws_data[0]
            log_info(f"🔒 [PTB LOCKED] Candle open PTB Strike: ${ptb:,.2f}")
            return ptb
        time.sleep(0.02)
    return None

def fetch_market_tokens(slug: str):
    url = f"{GAMMA_HOST}/events?slug={slug}"
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        events = r.json()
        if not events: return None
        markets = events[0].get("markets", [])
        if not markets: return None
        m = markets[0]
        clob_ids = json.loads(m.get("clobTokenIds", "[]"))
        outcomes = json.loads(m.get("outcomes", "[]"))
        if len(clob_ids) < 2 or len(outcomes) < 2: return None
        up_id = clob_ids[0] if outcomes[0].upper() == "UP" else clob_ids[1]
        down_id = clob_ids[1] if outcomes[0].upper() == "UP" else clob_ids[0]
        return {
            "slug": slug,
            "condition_id": m.get("conditionId"),
            "up_id": up_id,
            "down_id": down_id,
        }
    except Exception as e:
        log_info(f"⚠️ Error fetching market metadata: {e}")
        return None

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
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=3)
        resp = clob_client.get_balance_allowance(params)
        raw_bal = float(resp.get("balance", 0))
        return raw_bal / 1_000_000.0
    except Exception as e:
        return None

def check_sudden_trend(ptb: float, cur_price: float, v3: float, v5: float):
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

def execute_trend_scalp(ws: WSFeed, ptb: float, w_end: int, market: dict, clob_client=None):
    global window_trade_done, current_scalp, btc_price, current_bankroll, consecutive_wins, is_halted, halt_reason

    if is_halted:
        log_info(f"🛑 [BOT HALTED] Trading stopped permanently ({halt_reason}). No orders will be placed.")
        return

    trade_stake = round(current_bankroll, 2)
    log_info(f"🔍 Monitoring for sudden trend bursts in window {slug_for(w_end - WINDOW_SECS)} (PTB: ${ptb:,.2f} | Stake: ${trade_stake:.2f})...")
    
    with scalp_lock:
        current_scalp["active"] = False
        current_scalp["state"]  = "SCANNING"

    while True:
        now       = time.time()
        remaining = w_end - now

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
                            if isinstance(resp, dict) and resp.get("takingAmount"):
                                shares = math.floor(float(resp["takingAmount"]) * 100) / 100.0
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

                sold_successfully = True
                if clob_client is not None:
                    try:
                        from py_clob_client_v2 import MarketOrderArgsV2
                        log_info(f"🚀 [LIVE SELL] Placing market SELL order for {shares:.2f} shares of {side}...")
                        resp = clob_client.create_and_post_market_order(
                            order_args=MarketOrderArgsV2(
                                token_id=token_id, amount=shares, side="SELL"
                            )
                        )
                        log_info(f"✅ [LIVE SELL FILLED] Response: {resp}")
                    except Exception as e:
                        log_info(f"❌ [SELL ERROR] {e} — Retrying precision...")
                        try:
                            safe_shares = math.floor(shares * 10) / 10.0
                            resp = clob_client.create_and_post_market_order(
                                order_args=MarketOrderArgsV2(
                                    token_id=token_id, amount=safe_shares, side="SELL"
                                )
                            )
                            log_info(f"✅ [LIVE SELL RETRY FILLED] Response: {resp}")
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

    load_state()

    ws = WSFeed()
    ws.start()

    log_info("🚀 In-and-Out Sudden Trend Scalper Bot is active!")

    while True:
        try:
            now = time.time()
            w_start = win_start(now)
            w_end   = win_end(now)
            slug    = slug_for(w_start)

            window_trade_done = False

            if clob_client:
                bal = get_live_balance(clob_client)
                if bal is not None:
                    wallet_balance = bal

            market = fetch_market_tokens(slug)
            if not market:
                log_info(f"⚠️ Could not load market tokens for {slug}. Waiting 5s...")
                time.sleep(5)
                continue

            ptb = fetch_ptb_strike(ws, w_start)
            btc_ptb = ptb

            if ptb is not None:
                execute_trend_scalp(ws, ptb, w_end, market, clob_client)

            # Sleep until next window start
            sleep_sec = max(0.5, (w_end - time.time()) + 0.1)
            time.sleep(sleep_sec)

        except Exception as e:
            log_info(f"❌ Main loop exception: {e}")
            time.sleep(2)

if __name__ == "__main__":
    t = threading.Thread(target=bot_thread_worker, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
