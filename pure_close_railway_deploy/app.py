#!/usr/bin/env python3
"""
app.py — Pure Close-to-Market Rollover Bot + Live Web Console Dashboard for Railway
"""

import json
import os
import ssl
import sys
import time
import datetime
import threading
import logging
from collections import deque
from flask import Flask, jsonify, render_template
import requests
import websocket
from dotenv import load_dotenv

load_dotenv()

# ── Environment & Config ────────────────────────────────────────────────────────
POLYMARKET_LIVE_TRADING   = os.getenv("POLYMARKET_LIVE_TRADING", "False").lower() in ("true", "1", "yes")
POLYMARKET_ADDRESS        = os.getenv("POLYMARKET_ADDRESS")
POLYMARKET_API_KEY        = os.getenv("POLYMARKET_API_KEY")
POLYMARKET_API_SECRET     = os.getenv("POLYMARKET_API_SECRET")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE")
POLYMARKET_PRIVATE_KEY    = os.getenv("POLYMARKET_PRIVATE_KEY")

# Configurable Starting Stake (Set STARTING_STAKE_USD in Railway environment or .env)
STARTING_STAKE_USD = float(os.getenv("STARTING_STAKE_USD", "1.00"))

LIVE_WS_URL   = "wss://ws-live-data.polymarket.com/"
GAMMA_HOST    = "https://gamma-api.polymarket.com"
CLOB_HOST     = "https://clob.polymarket.com"
WINDOW_SECS   = 300          # 5-minute window

WAKE_UP_BEFORE       = 10   # wake up T-10s before close
PROBE_MARKS          = [8, 7, 6, 5, 4, 3, 2]
BET_WINDOW_START     = 8    # start betting at T-8s (catch open asks before dry up)
BET_WINDOW_END       = 2    # last bet at T-2s

CONFIDENCE_THRESHOLD = 0.55 # low threshold = almost always bet
MIN_ENTRY_PRICE      = 0.15 # Never buy garbage residual asks (< 15¢)

SETTLE_POLL_INTERVAL = 5
SETTLE_MAX_ATTEMPTS  = 60

STATE_FILE = "sprint_state.json"

# ── Global Shared State for Web Dashboard ───────────────────────────────────────
current_stake = STARTING_STAKE_USD
wins_streak   = 0
wallet_balance= 0.00
btc_price     = 0.00
btc_ptb       = 0.00
market_title  = "Waiting for market..."
window_str    = "Initializing..."
status_message= "Starting bot..."

trade_history = deque(maxlen=25)
console_logs  = deque(maxlen=60)
state_lock    = threading.Lock()


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    formatted = f"[{ts}] {msg}"
    print(formatted)
    with state_lock:
        console_logs.append(formatted)


def save_state():
    with state_lock:
        data = {
            "stake": current_stake,
            "wins": wins_streak,
            "updated_at": datetime.datetime.now().isoformat()
        }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log(f"⚠️ Error saving state: {e}")


def load_state():
    global current_stake, wins_streak
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                current_stake = float(data.get("stake", STARTING_STAKE_USD))
                wins_streak   = int(data.get("wins", 0))
                log(f"💾 Loaded state from file: Stake=${current_stake:.2f}, Wins={wins_streak}")
        except Exception as e:
            log(f"⚠️ Could not load state file: {e}")


# ── SSL + WS Feed ───────────────────────────────────────────────────────────────
def make_ssl_ctx():
    ctx = ssl.create_default_context()
    for p in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(p):
            ctx.load_verify_locations(p)
            break
    return ctx

WS_HEADERS = {
    "Origin": "https://polymarket.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
}

class WSFeed:
    def __init__(self):
        self._price   = None
        self._ts_ms   = None
        self._lock    = threading.Lock()
        self._ready   = threading.Event()
        self._ws_app  = None

    def start(self):
        ctx = make_ssl_ctx()

        def on_open(ws):
            ws.send(json.dumps({
                "action": "subscribe",
                "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}],
            }))

        def on_message(ws, raw):
            global btc_price
            if not raw: return
            try: msg = json.loads(raw)
            except Exception: return
            if msg.get("topic") != "crypto_prices_chainlink": return
            p = msg.get("payload", {})
            if p.get("symbol") != "btc/usd": return
            val = float(p.get("value", 0))
            ts  = p.get("timestamp")
            with self._lock:
                self._price = val
                self._ts_ms = ts
                self._ready.set()
            with state_lock:
                btc_price = val

        def on_close(ws, c, m):
            log("⚠️ WS connection closed — reconnecting in 2s...")
            time.sleep(2)
            self.start()

        def on_error(ws, e): pass

        app = websocket.WebSocketApp(
            LIVE_WS_URL, header=WS_HEADERS,
            on_open=on_open, on_message=on_message,
            on_close=on_close, on_error=on_error
        )
        self._ws_app = app
        threading.Thread(
            target=lambda: app.run_forever(sslopt={"context": ctx}, ping_interval=20, ping_timeout=10),
            daemon=True
        ).start()
        self._ready.wait(timeout=20)

    def latest(self):
        self._check_stale()
        with self._lock:
            return (self._price, self._ts_ms) if self._price is not None else None

    def price_at_or_after(self, ts_sec):
        self._check_stale()
        with self._lock:
            if self._ts_ms and self._price and self._ts_ms >= ts_sec * 1000:
                return self._price, self._ts_ms
        return None

    def _check_stale(self):
        with self._lock:
            if self._ts_ms and (time.time() - self._ts_ms / 1000) > 15:
                log("⚠️ WS feed stale — reconnecting...")
                self._ts_ms = self._price = None
                if self._ws_app:
                    try: self._ws_app.close()
                    except Exception: pass


# ── Market / Resolution APIs ────────────────────────────────────────────────────
def resolve_market(slug, timeout=10):
    r = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=timeout)
    r.raise_for_status()
    evts = r.json()
    if not evts: return None
    mkt  = evts[0]["markets"][0]
    tids = json.loads(mkt.get("clobTokenIds") or "[]")
    outs = [str(o).lower() for o in json.loads(mkt.get("outcomes") or "[]")]
    up_id = dn_id = None
    for i, o in enumerate(outs):
        if o in ("up", "yes"):    up_id = tids[i]
        elif o in ("down", "no"): dn_id = tids[i]
    if not up_id: up_id = tids[0]
    if not dn_id: dn_id = tids[1]
    return {"slug": slug, "title": mkt.get("question", slug), "up_id": up_id, "down_id": dn_id}


def probe_book(token_id, timeout=2):
    try:
        r = requests.get(f"{CLOB_HOST}/book", params={"token_id": token_id}, timeout=timeout)
        r.raise_for_status()
        asks = r.json().get("asks", [])
        if not asks: return None, 0
        return float(min(asks, key=lambda a: float(a["price"]))["price"]), len(asks)
    except Exception:
        return None, 0


def check_resolution(slug):
    try:
        r = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=5)
        r.raise_for_status()
        evts = r.json()
        if not evts: return None, []
        mkt  = evts[0]["markets"][0]
        prices = [float(p) for p in json.loads(mkt.get("outcomePrices") or "[]")]
        if prices and max(prices) >= 0.99:
            return prices[0] >= 0.99, prices
        return None, prices
    except Exception:
        return None, []


def update_live_balance(client):
    global wallet_balance
    if not client: return
    try:
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
        resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        bal = float(resp.get("balance", 0)) / 1_000_000
        with state_lock:
            wallet_balance = bal
    except Exception as e:
        log(f"⚠️ Error reading wallet balance: {e}")


def reconstruct_stake(client):
    try:
        from py_clob_client_v2.clob_types import TradeParams
        trades = client.get_trades(TradeParams(maker_address=POLYMARKET_ADDRESS))
        if not trades:
            log("ℹ️ No previous trades found. Using default starting stake.")
            return STARTING_STAKE_USD
        t = trades[0]
        match_time = int(float(t.get("match_time", 0)))
        w_s        = (match_time // 300) * 300
        slug       = f"btc-updown-5m-{w_s}"
        log(f"🔍 Reconstructing from last traded market: {slug}")
        up_won, _ = check_resolution(slug)
        if up_won is None:
            cost = float(t.get("size", 0)) * float(t.get("price", 0))
            log(f"⚠️ Unresolved market. Using last trade cost: ${cost:.2f}")
            return max(STARTING_STAKE_USD, round(cost, 2))
        outcome = t.get("outcome", "").upper()
        winner  = "UP" if up_won else "DOWN"
        if outcome == winner:
            pay = float(t.get("size", 0))
            log(f"🏆 Last trade WON! Rolled payout stake: ${pay:.2f}")
            return round(pay, 2)
        else:
            log(f"❌ Last trade LOST. Starting fresh at ${STARTING_STAKE_USD:.2f}")
            return STARTING_STAKE_USD
    except Exception as e:
        log(f"⚠️ Reconstruct error: {e}")
        return STARTING_STAKE_USD


# ── Signal Selection ────────────────────────────────────────────────────────────
def pick_side(up_ask, dn_ask, last_price, ptb):
    btc_dir = "UP" if last_price >= ptb else "DOWN"

    if up_ask is not None and dn_ask is not None:
        if up_ask > dn_ask and up_ask >= CONFIDENCE_THRESHOLD:
            target_side, target_ask = "UP", up_ask
        elif dn_ask > up_ask and dn_ask >= CONFIDENCE_THRESHOLD:
            target_side, target_ask = "DOWN", dn_ask
        else:
            target_side = btc_dir
            target_ask = up_ask if btc_dir == "UP" else dn_ask

        if target_side != btc_dir:
            log(f"⚠️ Signal conflict: Orderbook={target_side} vs BTC={btc_dir} -> REJECT")
            return None, None

        if target_ask is not None and target_ask >= MIN_ENTRY_PRICE:
            return target_side, target_ask
        return None, None

    elif up_ask is None and dn_ask is not None:
        if btc_dir == "UP":
            log(f"⚠️ UP side dried up -> UP won! Rejecting DOWN ask at ${dn_ask:.4f}")
            return None, None
        return None, None

    elif dn_ask is None and up_ask is not None:
        if btc_dir == "DOWN":
            log(f"⚠️ DOWN side dried up -> DOWN won! Rejecting UP ask at ${up_ask:.4f}")
            return None, None
        return None, None

    return None, None


# ── Probe + Bet Loop ────────────────────────────────────────────────────────────
def run_probe_phase(ws, ptb, w_end, market, clob_client=None, stake_usd=1.00):
    last_tick  = None
    last_price = ptb
    ticks      = 0
    done       = set()
    results    = []
    side = price = None

    log(f"🎯 PURE CLOSE BOT — Final {WAKE_UP_BEFORE}s | PTB=${ptb:,.2f} | Stake=${stake_usd:.2f}")

    while True:
        now = time.time()
        rem = w_end - now
        if rem <= -3: break

        ws_data = ws.latest()
        if ws_data:
            pr, ts = ws_data
            if ts != last_tick:
                last_tick  = ts
                last_price = pr
                ticks += 1
                diff  = pr - ptb
                arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "─")
                if ticks % 5 == 0:
                    log(f"tick #{ticks} {datetime.datetime.fromtimestamp(ts/1000).strftime('%H:%M:%S')} ${pr:,.2f} {arrow}{diff:+7.2f} ptb=${ptb:,.2f} ({int(rem)}s left)")

        for mark in PROBE_MARKS:
            if mark in done: continue
            if rem > mark:   continue
            done.add(mark)

            up_ask, n_up = probe_book(market["up_id"])
            dn_ask, n_dn = probe_book(market["down_id"])
            has_liq = (up_ask is not None or dn_ask is not None)
            in_bet  = (BET_WINDOW_END <= mark <= BET_WINDOW_START)
            st_str  = "OPEN" if has_liq else "CLOSED"
            u_str   = f"${up_ask:.4f}" if up_ask else "NONE"
            d_str   = f"${dn_ask:.4f}" if dn_ask else "NONE"
            phase   = "BET ZONE" if in_bet else "OBSERVE"

            log(f"► PROBE T-{mark}s UP={u_str} DN={d_str} BTC=${last_price:,.2f} [{st_str}] [{phase}]")

            results.append({
                "mark": mark, "ts": now, "up_ask": up_ask, "down_ask": dn_ask,
                "has_liquidity": has_liq, "bet_placed": False, "observe_only": not in_bet
            })

            if in_bet and side is None:
                if not has_liq:
                    log(f"🚫 T-{mark}s: No liquidity — skipping probe...")
                    continue

                s, ask = pick_side(up_ask, dn_ask, last_price, ptb)
                if s is None:
                    log(f"🚫 T-{mark}s: Cannot determine side — skipping...")
                    continue

                side  = s
                price = ask
                payout = stake_usd / price
                profit = payout - stake_usd
                results[-1]["bet_placed"] = True

                order_msg = "PAPER BET"
                if clob_client is not None:
                    order_msg = "LIVE BET"
                    log(f"🚀 PLACING LIVE ORDER: {side} @ ${price:.4f} (stake=${stake_usd:.2f})...")
                    try:
                        from py_clob_client_v2 import MarketOrderArgsV2
                        tid  = market["up_id"] if side == "UP" else market["down_id"]
                        resp = clob_client.create_and_post_market_order(
                            order_args=MarketOrderArgsV2(token_id=tid, amount=stake_usd, side="BUY")
                        )
                        log(f"✅ Live order response: {resp}")
                    except Exception as e:
                        log(f"❌ Order failed: {e}")
                        order_msg = "LIVE BET (FAILED)"
                        side = price = None
                        results[-1]["bet_placed"] = False
                        continue

                log(f"🎯 {order_msg} -> {side} @ ${price:.4f} (T-{mark}s) | Payout: ${payout:.4f} Profit: +${profit:.4f}")

        time.sleep(0.1)

    return results, side, price, last_price


# ── Settlement Background Worker ────────────────────────────────────────────────
def settle(slug, side, entry, stake):
    log(f"⏳ Polling settlement for market: {slug}...")
    for attempt in range(1, SETTLE_MAX_ATTEMPTS + 1):
        time.sleep(SETTLE_POLL_INTERVAL)
        up_won, prices = check_resolution(slug)
        if up_won is not None:
            actual = "UP" if up_won else "DOWN"
            won    = (side == "UP" and up_won) or (side == "DOWN" and not up_won)
            pnl    = stake * (1 / entry - 1) if won else -stake

            log(f"🏆 RESULT for {slug}: {'WIN ✅' if won else 'LOSS ❌'} | Bet: {side} | Outcome: {actual} | P&L: ${pnl:+.4f}")

            with state_lock:
                trade_history.appendleft({
                    "slug": slug.replace("btc-updown-5m-", ""),
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                    "side": side,
                    "price": entry,
                    "stake": stake,
                    "won": won,
                    "pnl": round(pnl, 4)
                })
            return won
    log(f"⚠️ Market {slug} did not resolve within wait time.")
    return None


# ── Core Trading Engine Thread ──────────────────────────────────────────────────
def bot_loop():
    global current_stake, wins_streak, btc_ptb, market_title, window_str, status_message

    mode_str = "LIVE TRADING" if POLYMARKET_LIVE_TRADING else "PAPER TRADING"
    log(f"🚀 Bot Engine Started ({mode_str}). Configured Starting Stake: ${STARTING_STAKE_USD:.2f}")

    clob_client = None
    if POLYMARKET_LIVE_TRADING:
        log("Initializing Polymarket CLOB client...")
        if not all([POLYMARKET_ADDRESS, POLYMARKET_API_KEY, POLYMARKET_API_SECRET, POLYMARKET_API_PASSPHRASE, POLYMARKET_PRIVATE_KEY]):
            log("❌ Missing live credentials in environment variables!")
            return
        try:
            from py_clob_client_v2 import ClobClient, ApiCreds
            from eth_account import Account

            eoa = Account.from_key(POLYMARKET_PRIVATE_KEY).address
            sig_type = 0
            funder   = None
            if POLYMARKET_ADDRESS and POLYMARKET_ADDRESS.lower() != eoa.lower():
                sig_type = 3
                funder   = POLYMARKET_ADDRESS
                log(f"👉 Using Proxy Wallet: {funder} (POLY_1271)")
            else:
                log(f"👉 Using EOA Wallet: {eoa}")

            creds = ApiCreds(
                api_key=POLYMARKET_API_KEY,
                api_secret=POLYMARKET_API_SECRET,
                api_passphrase=POLYMARKET_API_PASSPHRASE
            )
            clob_client = ClobClient(
                host=CLOB_HOST, chain_id=137,
                key=POLYMARKET_PRIVATE_KEY, creds=creds,
                signature_type=sig_type, funder=funder
            )
            log("✅ CLOB Client initialized successfully.")
        except Exception as e:
            log(f"❌ Error initializing CLOB client: {e}")
            return

    # Start WS feed
    ws = WSFeed()
    ws.start()
    for _ in range(40):
        if ws.latest(): break
        time.sleep(0.5)

    if not ws.latest():
        log("❌ Could not connect to WS feed!")
        return

    update_live_balance(clob_client)

    # Initial stake configuration (Non-interactive cloud startup)
    load_state()
    if POLYMARKET_LIVE_TRADING and clob_client:
        reconstructed = reconstruct_stake(clob_client)
        if reconstructed > STARTING_STAKE_USD:
            current_stake = reconstructed
            log(f"🔄 Reconstructed active rollover stake from trade history: ${current_stake:.2f}")
        else:
            current_stake = STARTING_STAKE_USD
            log(f"📌 Starting streak at default stake: ${current_stake:.2f}")

    save_state()

    # Main continuous loop
    while True:
        try:
            update_live_balance(clob_client)

            now       = time.time()
            w_s       = int(now // WINDOW_SECS) * WINDOW_SECS
            w_e       = w_s + WINDOW_SECS
            secs_into = now - w_s
            remaining = w_e - now

            start_t = datetime.datetime.fromtimestamp(w_s).strftime("%H:%M:%S")
            end_t   = datetime.datetime.fromtimestamp(w_e).strftime("%H:%M:%S")
            w_label = f"{start_t} → {end_t}"

            with state_lock:
                window_str     = w_label
                status_message = f"In window ({int(secs_into)}s in, {int(remaining)}s left)"

            log(f"═"*60)
            log(f"🆕 NEW CYCLE | Window: {w_label} | Current Stake: ${current_stake:.2f}")

            if secs_into > 10:
                sleep_secs = w_e - time.time() + 0.5
                log(f"⚠️ Mid-window detected ({int(secs_into)}s in). Sleeping {int(sleep_secs)}s...")
                time.sleep(max(0, sleep_secs))
                now = time.time()
                w_s = int(now // WINDOW_SECS) * WINDOW_SECS
                w_e = w_s + WINDOW_SECS

            slug = f"btc-updown-5m-{w_s}"
            log("Waiting for Price to Beat (PTB)...")

            ptb = None
            deadline = time.time() + 30
            while time.time() < deadline:
                r = ws.price_at_or_after(w_s)
                if r:
                    ptb, ts_ms = r
                    with state_lock: btc_ptb = ptb
                    log(f"📌 PRICE TO BEAT: ${ptb:,.2f}")
                    break
                time.sleep(0.1)

            if ptb is None:
                log("❌ Could not get PTB — skipping window.")
                time.sleep(max(10, w_e - time.time()))
                continue

            market = None
            for _ in range(20):
                try:
                    market = resolve_market(slug)
                    if market: break
                except Exception: pass
                time.sleep(2)

            if not market:
                log("❌ Could not resolve market — skipping window.")
                time.sleep(max(10, w_e - time.time()))
                continue

            with state_lock:
                market_title = market["title"]

            log(f"📋 {market['title']}")

            wake_at   = w_e - WAKE_UP_BEFORE
            wait_secs = wake_at - time.time()
            if wait_secs > 0:
                log(f"⏳ Sleeping {int(wait_secs)}s — waking up at T-{WAKE_UP_BEFORE}s...")
                time.sleep(wait_secs)

            results, side, entry, last_price = run_probe_phase(
                ws, ptb, w_e, market, clob_client=clob_client, stake_usd=current_stake
            )

            if side and entry:
                actual = "UP" if last_price > ptb else "DOWN"
                won    = (side == actual)
                old_stake = current_stake

                if won:
                    with state_lock:
                        wins_streak += 1
                        current_stake = round(old_stake / entry, 2)
                    log(f"💰 WIN! Streak: {wins_streak} | Rolled over -> next stake: ${current_stake:.2f}")
                else:
                    with state_lock:
                        wins_streak   = 0
                        current_stake = STARTING_STAKE_USD
                    log(f"❌ LOSS! Streak reset -> stake: ${current_stake:.2f}")

                save_state()
                threading.Thread(target=settle, args=(slug, side, entry, old_stake), daemon=True).start()
            else:
                log("ℹ️ No bet placed this window. Stake unchanged.")

            time.sleep(2)

        except Exception as e:
            log(f"❌ Main loop error: {e}")
            time.sleep(10)


# ── Flask Web App & Routes ──────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/state")
def get_state():
    with state_lock:
        return jsonify({
            "live_trading": POLYMARKET_LIVE_TRADING,
            "starting_stake_config": STARTING_STAKE_USD,
            "current_stake": current_stake,
            "wins_streak": wins_streak,
            "wallet_balance": wallet_balance,
            "btc_price": btc_price,
            "btc_ptb": btc_ptb,
            "market_title": market_title,
            "window_str": window_str,
            "status_message": status_message,
            "trade_history": list(trade_history),
            "console_logs": list(console_logs)
        })

# Start background trading thread when Flask app initializes
threading.Thread(target=bot_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
