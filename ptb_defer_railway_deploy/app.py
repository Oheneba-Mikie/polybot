"""
================================================================================
PTB-DEFER GUARD BOT — CLOUD ENGINE & WEB DASHBOARD
================================================================================
Rule:
If price gap < $5.00 at T-8s to T-3s -> DO NOT STAKE. Wait for T-2s!
At T-2s: Check live BTC direction vs PTB again ("UP" if BTC >= PTB else "DOWN").
Stake on the NEW direction at T-2s!
================================================================================
"""

import os, sys, time, json, datetime, ssl, threading, requests, traceback
from flask import Flask, render_template, jsonify

app = Flask(__name__)

bot_state = {
    "balance": 0.0,
    "stake": 1.0,
    "double_stake": True,
    "streak": 0,
    "wins": 0,
    "losses": 0,
    "skipped": 0,
    "paused": False,
    "history": [],
    "logs": []
}

def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    bot_state["logs"].append(formatted)
    if len(bot_state["logs"]) > 200:
        bot_state["logs"].pop(0)

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"
LIVE_WS_URL= "wss://ws-live-data.polymarket.com/"

POLYMARKET_LIVE_TRADING = os.getenv("POLYMARKET_LIVE_TRADING", "true").lower() == "true"
DOUBLE_STAKE            = os.getenv("DOUBLE_STAKE", "true").lower() == "true"
CLOSE_PTB_THRESHOLD     = float(os.getenv("CLOSE_PTB_THRESHOLD", "50.00"))
CONFIDENCE_THRESHOLD    = float(os.getenv("CONFIDENCE_THRESHOLD", "0.85"))
MIN_ENTRY_PRICE         = float(os.getenv("MIN_ENTRY_PRICE", "0.15"))
STARTING_STAKE_USD      = float(os.getenv("STARTING_STAKE_USD", "1.00"))

bot_state["double_stake"] = DOUBLE_STAKE

POLYMARKET_ADDRESS        = os.getenv("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY        = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET     = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY    = os.getenv("POLYMARKET_PRIVATE_KEY", "")

WAKE_UP_BEFORE   = 10
BET_WINDOW_START = 8
BET_WINDOW_END   = 2
PROBE_MARKS      = [8, 7, 6, 5, 4, 3, 2]
WINDOW_SECS      = 300
SETTLE_POLL_INTERVAL = 5
SETTLE_MAX_ATTEMPTS  = 60

def make_ssl_ctx():
    ctx = ssl.create_default_context()
    for p in ["/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"]:
        if os.path.exists(p):
            ctx.load_verify_locations(p); break
    return ctx

WS_HEADERS = {
    "Origin": "https://polymarket.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PTBDeferCloudBot/1.0"
}

def win_start(ts=None):
    t = ts if ts is not None else time.time()
    return int(t // WINDOW_SECS) * WINDOW_SECS

def win_end(ts=None):
    return win_start(ts) + WINDOW_SECS

def slug_for(ts=None):
    return f"btc-updown-5m-{win_start(ts)}"


class WSFeed:
    def __init__(self):
        self._price = self._ts_ms = None
        self._lock  = threading.Lock()
        self._ready = threading.Event()
        self._ws_app = None

    def start(self):
        ctx = make_ssl_ctx()

        def on_open(ws):
            ws.send(json.dumps({"action": "subscribe",
                "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}]}))

        def on_message(ws, raw):
            if not raw: return
            try: msg = json.loads(raw)
            except Exception: return
            if msg.get("topic") != "crypto_prices_chainlink": return
            p = msg.get("payload", {})
            if p.get("symbol") != "btc/usd": return
            with self._lock:
                self._price = p.get("value")
                self._ts_ms = p.get("timestamp")
                self._ready.set()

        def on_close(ws, c, m):
            time.sleep(2); self.start()

        def on_error(ws, e): pass

        import websocket
        app = websocket.WebSocketApp(LIVE_WS_URL, header=WS_HEADERS,
            on_open=on_open, on_message=on_message,
            on_close=on_close, on_error=on_error)
        self._ws_app = app
        threading.Thread(
            target=lambda: app.run_forever(sslopt={"context": ctx}, ping_interval=20, ping_timeout=10),
            daemon=True).start()
        self._ready.wait(timeout=20)

    def latest(self):
        self._stale_check()
        with self._lock:
            return (self._price, self._ts_ms) if self._price is not None else None

    def price_at_or_after(self, ts_sec):
        self._stale_check()
        with self._lock:
            if self._ts_ms and self._price and self._ts_ms >= ts_sec * 1000:
                return self._price, self._ts_ms
        return None

    def _stale_check(self):
        with self._lock:
            if self._ts_ms and (time.time() - self._ts_ms / 1000) > 15:
                log("  [WS] Stale feed detected (>15s) - forcing reconnect...")
                self._ts_ms = self._price = None
                if self._ws_app:
                    try: self._ws_app.close()
                    except Exception: pass


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


def get_live_balance(client):
    try:
        try:
            from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
        except ImportError:
            from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
        resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        return float(resp.get("balance", 0)) / 1_000_000
    except Exception as e:
        log(f"  WARNING balance: {e}"); return None


def post_market_order_safe(client, token_id, amount, price, side="BUY"):
    try:
        try:
            from py_clob_client.clob_types import MarketOrderArgs, OrderType
        except ImportError:
            from py_clob_client_v2.clob_types import MarketOrderArgsV2 as MarketOrderArgs, OrderType

        mo = MarketOrderArgs(token_id=token_id, amount=float(amount), price=float(price), side=side)
        signed = client.create_market_order(mo)
        return client.post_order(signed, OrderType.FOK)
    except Exception as e:
        log(f"  Execution Error: {e}")
        return None


def pick_side(up_ask, dn_ask, last_price, ptb):
    btc_dir = "UP" if last_price >= ptb else "DOWN"
    target_ask = up_ask if btc_dir == "UP" else dn_ask

    if target_ask is None:
        return btc_dir, 0.99

    if target_ask >= CONFIDENCE_THRESHOLD:
        return btc_dir, target_ask

    return None, None


def evaluate_ptb_defer_rule(up_ask, dn_ask, last_price, ptb, mark):
    btc_gap = abs(last_price - ptb)
    btc_dir = "UP" if last_price >= ptb else "DOWN"

    s, ask = pick_side(up_ask, dn_ask, last_price, ptb)

    if mark > 2:
        if btc_gap < CLOSE_PTB_THRESHOLD:
            return None, None, False, f"T-{mark}s: Gap (${btc_gap:.2f}) close to PTB (< ${CLOSE_PTB_THRESHOLD:.2f}) -> Deferring to T-2s!"
        return s, ask, (s is not None), f"T-{mark}s: Normal bet (Gap=${btc_gap:.2f} >= ${CLOSE_PTB_THRESHOLD:.2f})"
    else:  # T-2s
        final_dir = btc_dir
        final_ask = up_ask if final_dir == "UP" else dn_ask
        if final_ask is None:
            return final_dir, 0.99, True, f"T-2s FINAL STAKE: {final_dir} (Dried up / locked in)"
        if final_ask >= MIN_ENTRY_PRICE:
            return final_dir, final_ask, True, f"T-2s FINAL STAKE: {final_dir} @ ${final_ask:.4f}"
        return None, None, False, "T-2s: Final ask price below minimum (15¢)"


def run_bot_engine():
    log("Starting PTB-Defer Guard Bot Cloud Engine...")
    client = None

    if POLYMARKET_LIVE_TRADING:
        log("Initializing CLOB Client...")
        try:
            from py_clob_client_v2 import ClobClient, ApiCreds

            from eth_account import Account
            eoa = Account.from_key(POLYMARKET_PRIVATE_KEY).address
            sig_type = 0; funder = None
            if POLYMARKET_ADDRESS and POLYMARKET_ADDRESS.lower() != eoa.lower():
                sig_type = 3; funder = POLYMARKET_ADDRESS
                log(f"Proxy Wallet: {funder}  sig_type=3")
            creds  = ApiCreds(api_key=POLYMARKET_API_KEY, api_secret=POLYMARKET_API_SECRET,
                              api_passphrase=POLYMARKET_API_PASSPHRASE)
            client = ClobClient(host=CLOB_HOST, chain_id=137, key=POLYMARKET_PRIVATE_KEY,
                                creds=creds, signature_type=sig_type, funder=funder)
            log("CLOB Client OK.")
        except Exception as e:
            log(f"ERROR initializing client: {e}")

    ws = WSFeed(); ws.start()
    for _ in range(40):
        if ws.latest(): break
        time.sleep(0.5)

    btc, _ = ws.latest() or (0, 0)
    log(f"WS Feed Active. Live BTC: ${btc:,.2f}")

    stake = STARTING_STAKE_USD
    bot_state["stake"] = stake

    while True:
        try:
            if bot_state.get("paused", False):
                time.sleep(1)
                continue

            if client:
                bal = get_live_balance(client)
                if bal is not None: bot_state["balance"] = bal

            now  = time.time()
            w_s  = win_start(now)
            w_e  = win_end(now)
            into = now - w_s
            rem  = w_e - now

            log(f"--- NEW CYCLE | Window: {w_s} -> {w_e} | Stake: ${stake:.2f} ---")

            if into > 10:
                sl = w_e - time.time() + 0.5
                time.sleep(max(0, sl))
                now = time.time(); w_s = win_start(now); w_e = w_s + WINDOW_SECS

            slug = slug_for(w_s)
            ptb = None
            dl  = time.time() + 30
            while time.time() < dl:
                r = ws.price_at_or_after(w_s)
                if r: ptb, ts = r; break
                time.sleep(0.1)

            if ptb is None:
                log("Could not fetch PTB. Skipping.")
                time.sleep(max(10, w_e - time.time())); continue

            log(f"Window: {slug} | PTB: ${ptb:,.2f}")

            market = None
            for _ in range(20):
                market = resolve_market(slug)
                if market: break
                time.sleep(1)

            if not market:
                log("Market not found. Skipping.")
                time.sleep(max(10, w_e - time.time())); continue

            target_wake = w_e - WAKE_UP_BEFORE
            sleep_time  = target_wake - time.time()
            if sleep_time > 0: time.sleep(sleep_time)

            done = set()
            side = price = None
            last_price = ptb

            while True:
                rem = w_e - time.time()
                if rem <= -3: break

                ws_data = ws.latest()
                if ws_data: last_price = ws_data[0]

                for mark in PROBE_MARKS:
                    if mark in done or rem > mark: continue
                    done.add(mark)

                    up_ask, n_up = probe_book(market["up_id"])
                    dn_ask, n_dn = probe_book(market["down_id"])
                    in_bet  = (BET_WINDOW_END <= mark <= BET_WINDOW_START)

                    if in_bet and side is None:
                        s, ask, approved, reason = evaluate_ptb_defer_rule(up_ask, dn_ask, last_price, ptb, mark)
                        log(f"T-{mark}s Probe: BTC=${last_price:,.2f} | Status: {reason}")

                        if not approved or s is None:
                            if "Deferring" in reason: bot_state["deferred"] += 1
                            continue

                        side  = s
                        price = ask if ask else 0.99
                        single_stake = round(stake / 2.0, 2) if DOUBLE_STAKE else stake
                        if single_stake < 1.00: single_stake = stake

                        if client:
                            try:
                                from py_clob_client_v2 import MarketOrderArgsV2, OrderType
                                tid = market["up_id"] if side == "UP" else market["down_id"]
                                if DOUBLE_STAKE:
                                    log(f"[ORDER] LIVE DOUBLE STAKE (FAK): 2 x ${single_stake:.2f} on {side} @ ${price:.4f}")
                                    client.create_and_post_market_order(MarketOrderArgsV2(token_id=tid, amount=single_stake, price=price, side="BUY", order_type=OrderType.FAK))
                                    client.create_and_post_market_order(MarketOrderArgsV2(token_id=tid, amount=single_stake, price=price, side="BUY", order_type=OrderType.FAK))
                                else:
                                    log(f"[ORDER] LIVE SINGLE STAKE (FAK): ${single_stake:.2f} on {side} @ ${price:.4f}")
                                    client.create_and_post_market_order(MarketOrderArgsV2(token_id=tid, amount=single_stake, price=price, side="BUY", order_type=OrderType.FAK))
                            except Exception as e:
                                log(f"Execution Error: {e}")
                                side = None  # Order failed -> do not track as a filled trade!
                        else:
                            log(f"PAPER BET: {side} @ ${price:.4f}  stake=${stake:.2f}")

                time.sleep(0.05)

            if side:
                log(f"Polling settlement for {slug}...")
                win = None
                for _ in range(SETTLE_MAX_ATTEMPTS):
                    time.sleep(SETTLE_POLL_INTERVAL)
                    up_won, _ = check_resolution(slug)
                    if up_won is not None:
                        win = (side == "UP" and up_won) or (side == "DOWN" and not up_won)
                        break

                if win is True:
                    payout = stake / price if price else stake
                    stake  = round(payout, 2)
                    bot_state["streak"] += 1
                    bot_state["wins"] += 1
                    bot_state["stake"] = stake
                    log(f"🎉 WIN! Streak: {bot_state['streak']} | Rolled over -> next stake: ${stake:.2f}")
                elif win is False:
                    stake = STARTING_STAKE_USD
                    bot_state["streak"] = 0
                    bot_state["losses"] += 1
                    bot_state["stake"] = stake
                    log(f"❌ LOSS. Resetting stake -> ${stake:.2f}")
            else:
                log("No bet placed. Stake unchanged.")

            time.sleep(max(1, w_e - time.time()))

        except Exception as e:
            log(f"ERROR in engine loop: {e}")
            traceback.print_exc()
            time.sleep(10)

# Start engine thread
threading.Thread(target=run_bot_engine, daemon=True).start()

# Flask Routes
@app.route("/")
def index():
    return render_template("dashboard.html")

def fetch_blockchain_pnl_history():
    if not POLYMARKET_ADDRESS: return []
    try:
        r = requests.get("https://data-api.polymarket.com/activity", params={"user": POLYMARKET_ADDRESS, "limit": 100}, timeout=5)
        if r.status_code != 200: return []
        acts = sorted(r.json(), key=lambda x: x.get("timestamp", 0))

        points = []
        for a in acts[-30:]:
            ts = a.get("timestamp", 0)
            dt = datetime.datetime.fromtimestamp(ts, datetime.UTC).strftime("%H:%M GMT")
            a_type = a.get("type")
            usdc = float(a.get("usdcSize", 0))
            outcome = a.get("outcome", "")
            title = a.get("title", "")
            
            points.append({
                "time": dt,
                "type": a_type,
                "amount": usdc,
                "outcome": outcome,
                "title": title
            })
        return points
    except Exception as e:
        log(f"History fetch error: {e}")
        return []

@app.route("/api/status")
def api_status():
    pnl_pts = fetch_blockchain_pnl_history()
    return jsonify({
        "balance": bot_state["balance"],
        "stake": bot_state["stake"],
        "double_stake": bot_state["double_stake"],
        "streak": bot_state["streak"],
        "wins": bot_state["wins"],
        "losses": bot_state["losses"],
        "skipped": bot_state.get("deferred", bot_state.get("skipped", 0)),
        "paused": bot_state.get("paused", False),
        "history": pnl_pts,
        "logs": "\n".join(bot_state["logs"])
    })

@app.route("/api/toggle_pause", methods=["POST"])
def toggle_pause():
    bot_state["paused"] = not bot_state.get("paused", False)
    state_str = "PAUSED" if bot_state["paused"] else "RESUMED"
    log(f"⏸️ USER TOGGLED BOT: {state_str}")
    return jsonify({"paused": bot_state["paused"], "status": "ok"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
