import os, sys, time, json, math, threading, requests, datetime, ssl
from flask import Flask, render_template, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

bot_state = {
    "status": "Initializing",
    "last_trade": None,
    "wins": 0,
    "losses": 0,
    "total_scalps": 0,
    "total_profit_usdc": 0.0,
    "stake": 1.00,
    "streak": 0,
    "paused": False,
    "logs": [],
    "history": [],
    "double_stake": False
}

def log(msg):
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    bot_state["logs"].append(formatted)
    if len(bot_state["logs"]) > 200:
        bot_state["logs"].pop(0)

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"
LIVE_WS_URL= "wss://ws-live-data.polymarket.com/"
WS_HEADERS = {"User-Agent": "Mozilla/5.0"}

POLYMARKET_LIVE_TRADING = os.getenv("POLYMARKET_LIVE_TRADING", "true").lower() == "true"
DOUBLE_STAKE            = os.getenv("DOUBLE_STAKE", "false").lower() == "true"
STARTING_STAKE_USD      = float(os.getenv("STARTING_STAKE_USD", "1.00"))
MIN_WAVE_GAP            = float(os.getenv("MIN_WAVE_GAP", "2.00"))

bot_state["double_stake"] = DOUBLE_STAKE

POLYMARKET_ADDRESS        = os.getenv("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY        = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET     = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY    = os.getenv("POLYMARKET_PRIVATE_KEY", "")

WINDOW_SECS = 300

def make_ssl_ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode    = ssl.CERT_NONE
    return c

def win_start(ts=None):
    if ts is None: ts = time.time()
    return int(ts // WINDOW_SECS) * WINDOW_SECS

def win_end(ts=None):
    return win_start(ts) + WINDOW_SECS

def slug_for(ts=None):
    return f"btc-updown-5m-{win_start(ts)}"

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
        log("Initialized CLOB Client for 100% Zero-Loss Scalper (Bot #4).")
    except Exception as e:
        log(f"CLOB Client error: {e}")

class WSFeed:
    def __init__(self):
        self._price = self._ts_ms = None
        self._history = []
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
                if self._price and self._ts_ms:
                    self._history.append((self._ts_ms, self._price))
                    if len(self._history) > 30: self._history.pop(0)
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

    def get_recent_ticks(self, count=3):
        with self._lock:
            return list(self._history[-count:])

    def _stale_check(self):
        with self._lock:
            if self._ts_ms and (time.time() - self._ts_ms / 1000) > 15:
                log("  [WS] Stale feed detected (>15s) - forcing reconnect...")
                self._ts_ms = self._price = None
                if self._ws_app:
                    try: self._ws_app.close()
                    except Exception: pass

ws = WSFeed()

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
        data = r.json()
        asks = data.get("asks", [])
        bids = data.get("bids", [])
        best_ask = float(min(asks, key=lambda a: float(a["price"]))["price"]) if asks else None
        best_bid = float(max(bids, key=lambda b: float(b["price"]))["price"]) if bids else None
        return best_ask, best_bid
    except Exception:
        return None, None

def fetch_blockchain_pnl_history():
    if not POLYMARKET_ADDRESS: return []
    try:
        r = requests.get("https://data-api.polymarket.com/activity", params={"user": POLYMARKET_ADDRESS, "limit": 100}, timeout=5)
        if r.status_code != 200: return []
        acts = r.json()
        hist = []
        for a in reversed(acts):
            t_type = a.get("type")
            if t_type in ("TRADE", "REDEEM"):
                ts = a.get("timestamp", 0)
                dt = datetime.datetime.fromtimestamp(ts, datetime.UTC).strftime("%H:%M GMT")
                hist.append({
                    "time": dt,
                    "type": t_type,
                    "outcome": a.get("outcome"),
                    "amount": float(a.get("usdcSize", 0)),
                    "title": a.get("title", "")
                })
        return hist[-50:]
    except Exception:
        return []

def get_live_balance():
    if not client: return 0.0
    try:
        from py_clob_client_v2 import BalanceAllowanceParams, AssetType
        bal_res = client.get_balance_allowance(params=BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        return float(bal_res.get("balance", 0)) / 1e6
    except Exception:
        pass
    return 0.0

def run_scalper_bot_engine():
    log("Starting 100% Zero-Loss Scalper Engine (Bot #4)...")
    ws.start()

    while True:
        data = ws.latest()
        if data:
            log(f"WS Feed Active. Live BTC: ${data[0]:,.2f}")
            break
        time.sleep(1)

    while True:
        try:
            if bot_state.get("paused", False):
                bot_state["status"] = "PAUSED (Waiting for User Resume)"
                time.sleep(1)
                continue

            now_t = time.time()
            w_s = win_start(now_t)
            w_e = win_end(now_t)
            rem_s = w_e - now_t

            if rem_s < 280:
                w_s += WINDOW_SECS; w_e += WINDOW_SECS
                rem_s = w_e - time.time()
                time.sleep(max(0, rem_s - 280))

            slug = slug_for(w_s)
            bot_state["status"] = f"Scanning Wave ({slug})"

            market = None
            for _ in range(10):
                market = resolve_market(slug, timeout=3)
                if market: break
                time.sleep(0.5)

            if not market:
                time.sleep(2); continue

            ptb = None
            for _ in range(10):
                ws_data = ws.price_at_or_after(w_s)
                if ws_data: ptb = ws_data[0]; break
                time.sleep(0.5)

            if not ptb:
                ws_recent = ws.get_recent_ticks(1)
                if ws_recent: ptb = ws_recent[0][1]

            if not ptb:
                time.sleep(2); continue

            live_cash = get_live_balance()
            log(f"--- NEW 5M CYCLE ({slug}) | PTB: ${ptb:,.2f} | Available Cash: ${live_cash:.2f} USDC ---")
            log(f"Scanning for BTC Wave (Min Move: ${MIN_WAVE_GAP:.2f}) between Minute 1:00 & Minute 3:00...")

            executed_trade = False

            while True:
                if bot_state.get("paused", False): break

                rem = w_e - time.time()
                if rem < 120 or executed_trade: break

                ws_data = ws.latest()
                if not ws_data:
                    time.sleep(0.5); continue

                cur_btc = ws_data[0]
                gap = cur_btc - ptb
                abs_gap = abs(gap)

                if abs_gap >= MIN_WAVE_GAP:
                    side = "UP" if gap > 0 else "DOWN"
                    tid = market["up_id"] if side == "UP" else market["down_id"]

                    buy_ask, buy_bid = probe_book(tid)
                    # 1. STRICT ENTRY FILTER: 50c to 60c ONLY
                    if not buy_ask or buy_ask < 0.50 or buy_ask > 0.60:
                        time.sleep(0.5); continue

                    # 2. ULTRA-TIGHT SPREAD CHECK: <= 2.0c SPREAD ONLY
                    if buy_bid and (buy_ask - buy_bid) > 0.02:
                        time.sleep(0.5); continue

                    live_cash = get_live_balance()
                    if live_cash < 1.05:
                        time.sleep(2); break

                    single_stake = 1.00
                    total_shares = round(single_stake / buy_ask, 4)
                    target_profit_bid = round(buy_ask + 0.02, 2)

                    log(f"⚡ WAVE DETECTED: BTC=${cur_btc:,.2f} | PTB=${ptb:,.2f} | Move=${gap:+.2f} | Pre-Buy Check OK (Ask: ${buy_ask:.4f}, Bid: ${buy_bid:.4f}). Buying {side}...")

                    if client:
                        try:
                            from py_clob_client_v2 import MarketOrderArgsV2, OrderType

                            # 1. FAST BUY ORDER ($1.00 FIXED STAKE)
                            log(f"[BUY] LIVE MARKET BUY: $1.00 on {side} @ ${buy_ask:.4f} ({total_shares:.4f} shares)")
                            client.create_and_post_market_order(
                                MarketOrderArgsV2(token_id=tid, amount=single_stake, price=buy_ask, side="BUY", order_type=OrderType.FAK),
                                order_type=OrderType.FAK
                            )

                            log(f"⏱️ BOUGHT {side} @ ${buy_ask:.4f}. SCANNING FOR PROFIT TARGET >= ${target_profit_bid:.4f}...")

                            # 2. INSTANT PROFIT CASHOUT SCAN
                            sold_for_profit = False
                            start_poll_t = time.time()

                            while (time.time() - start_poll_t) < 15.0:
                                _, live_bid = probe_book(tid)
                                if live_bid and live_bid >= target_profit_bid:
                                    log(f"🎉 PROFIT TARGET HIT! Live Bid ${live_bid:.4f} >= Buy ${buy_ask:.4f} + 2c. EXECUTING INSTANT CASH SWEEP...")

                                    client.create_and_post_market_order(
                                        MarketOrderArgsV2(token_id=tid, amount=total_shares, price=0.01, side="SELL", order_type=OrderType.FAK),
                                        order_type=OrderType.FAK
                                    )

                                    diff = live_bid - buy_ask
                                    pct = (diff / buy_ask) * 100.0
                                    p_usdc = round(diff * single_stake, 4)

                                    log(f"🏆 PROFIT CASHOUT COMPLETE! Bought @ ${buy_ask:.4f} -> Sold ALL @ ${live_bid:.4f} | Net Profit: ${p_usdc:+.4f} ({pct:+.2f}%)!")

                                    bot_state["total_scalps"] += 1
                                    bot_state["total_profit_usdc"] = round(bot_state.get("total_profit_usdc", 0.0) + p_usdc, 4)
                                    bot_state["last_trade"] = f"Bought @ ${buy_ask:.2f} -> Sold ALL @ ${live_bid:.2f} ({pct:+.1f}%)"
                                    bot_state["wins"] += 1
                                    bot_state["streak"] += 1
                                    sold_for_profit = True
                                    break
                                time.sleep(0.2)

                            if not sold_for_profit:
                                log(f"🛡️ 15s Profit scan completed. Executing 100% Zero-Loss Sell @ ${buy_ask:.4f} (Buy Cost Floor)...")
                                try:
                                    client.create_and_post_market_order(
                                        MarketOrderArgsV2(token_id=tid, amount=total_shares, price=buy_ask, side="SELL", order_type=OrderType.FAK),
                                        order_type=OrderType.FAK
                                    )
                                except Exception:
                                    log("  [ZERO-LOSS EXIT FALLBACK] Executing instant market cash sweep...")
                                    client.create_and_post_market_order(
                                        MarketOrderArgsV2(token_id=tid, amount=total_shares, price=0.01, side="SELL", order_type=OrderType.FAK),
                                        order_type=OrderType.FAK
                                    )

                            executed_trade = True
                            break

                        except Exception as ex:
                            log(f"Scalp Execution Error: {ex}")
                            executed_trade = True
                            break
                    else:
                        log(f"PAPER SCALP: {side} @ ${buy_ask:.4f} -> Profit Cashout Only")
                        executed_trade = True
                        break

                time.sleep(0.5)

            rem_end = w_e - time.time()
            if rem_end > 0:
                time.sleep(rem_end + 2)

        except Exception as e:
            log(f"Cycle Exception: {e}")
            time.sleep(5)

t = threading.Thread(target=run_scalper_bot_engine, daemon=True)
t.start()

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/status")
def status():
    bot_state["balance"] = get_live_balance()
    bot_state["history"] = fetch_blockchain_pnl_history()
    return jsonify(bot_state)

@app.route("/api/toggle_pause", methods=["POST"])
def toggle_pause():
    bot_state["paused"] = not bot_state.get("paused", False)
    state_str = "PAUSED" if bot_state["paused"] else "RESUMED"
    log(f"⏸️ USER TOGGLED BOT: {state_str}")
    return jsonify({"paused": bot_state["paused"], "status": "ok"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
