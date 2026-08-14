import os, sys, time, json, math, ssl, datetime, threading, requests, websocket
from flask import Flask, render_template, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

bot_state = {
    "status": "Initializing",
    "mode": "LIVE TRADING" if os.getenv("POLYMARKET_LIVE_TRADING", "true").lower() == "true" else "PAPER TRADING",
    "spot_btc": None,
    "ptb": None,
    "current_slug": None,
    "last_signal": None,
    "total_trades": 0,
    "wins": 0,
    "losses": 0,
    "total_profit_usdc": 0.0,
    "logs": [],
    "history": []
}

def log(msg):
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    bot_state["logs"].append(formatted)
    if len(bot_state["logs"]) > 200:
        bot_state["logs"].pop(0)

CLOB_HOST = "https://clob.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"
LIVE_WS_URL = "wss://ws-live-data.polymarket.com/"
WINDOW_SECS = 300

MIN_EDGE = 0.15             # 15% mathematical edge required
MIN_BTC_MOVE = 2.50          # $2.50 min move from PTB (lowered for 10-min live test)
MIN_ASK_PRICE = 0.20        # REALITY CHECK: $0.20 min ask per share (blocks dead 4c/7c tickets)
MAX_ASK_PRICE = 0.45        # $0.45 max ask per share (micro-cents 5-share orders)
STAKE_USD = 1.00            # Micro stake budget
BTC_VOLATILITY = 0.50       # 50% annualized volatility
PROBE_INTERVAL = 1.5        # Seconds between book checks

POLYMARKET_LIVE_TRADING = False
POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")

# ── CLOB Client Setup ────────────────────────────────────────────────────────────
clob_client = None
if POLYMARKET_LIVE_TRADING:
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds
        creds = ApiCreds(
            api_key=POLYMARKET_API_KEY,
            api_secret=POLYMARKET_API_SECRET,
            api_passphrase=POLYMARKET_API_PASSPHRASE
        )
        clob_client = ClobClient(
            host=CLOB_HOST,
            chain_id=137,
            key=POLYMARKET_PRIVATE_KEY,
            creds=creds,
            signature_type=3,
            funder=POLYMARKET_ADDRESS
        )
        log("[SUCCESS] CLOB client initialized for live micro-trading.")
    except Exception as e:
        log(f"[ERROR] CLOB client initialization error: {e}")

def make_ssl_ctx():
    ctx = ssl.create_default_context()
    for cert_path in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(cert_path):
            ctx.load_verify_locations(cert_path)
            break
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

# ── Black-Scholes Formula ────────────────────────────────────────────────────────
def normal_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def calculate_true_probability(S, K, T_sec, sigma=BTC_VOLATILITY):
    if T_sec <= 0:
        return 1.0 if S >= K else 0.0
    T_years = T_sec / 31536000.0
    try:
        denom = sigma * math.sqrt(T_years)
        d2 = (math.log(S / K) - 0.5 * (sigma ** 2) * T_years) / denom
        return normal_cdf(d2)
    except ZeroDivisionError:
        return 1.0 if S >= K else 0.0
    except ValueError:
        return 0.5

# ── Polymarket Official Chainlink Feed ───────────────────────────────────────────
class PolymarketChainlinkWSFeed:
    def __init__(self):
        self._price = None
        self._ts_ms = None
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._stopped = False
        self._ws_app = None

    def start(self):
        ssl_ctx = make_ssl_ctx()

        def on_open(ws):
            ws.send(json.dumps({
                "action": "subscribe",
                "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}]
            }))

        def on_message(ws, raw):
            if not raw: return
            try:
                msg = json.loads(raw)
                if msg.get("topic") != "crypto_prices_chainlink": return
                p = msg.get("payload", {})
                if p.get("symbol") != "btc/usd": return
                val = p.get("value")
                ts = p.get("timestamp")
                if val is not None and ts is not None:
                    with self._lock:
                        self._price = float(val)
                        self._ts_ms = int(ts)
                        bot_state["spot_btc"] = self._price
                        self._ready.set()
            except Exception:
                pass

        def on_close(ws, c, m):
            if not self._stopped:
                time.sleep(2)
                self.start()

        def on_error(ws, err): pass

        self._ws_app = websocket.WebSocketApp(
            LIVE_WS_URL,
            header={"User-Agent": "Mozilla/5.0"},
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error
        )
        threading.Thread(
            target=lambda: self._ws_app.run_forever(sslopt={"context": ssl_ctx}, ping_interval=20, ping_timeout=10),
            daemon=True
        ).start()
        self._ready.wait(timeout=15)

    def latest(self):
        with self._lock:
            return (self._price, self._ts_ms) if self._price is not None else None

ws_feed = PolymarketChainlinkWSFeed()

def resolve_market_by_slug(slug):
    try:
        r = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=5)
        if r.status_code == 200:
            evts = r.json()
            if evts and "markets" in evts[0] and evts[0]["markets"]:
                mkt = evts[0]["markets"][0]
                tids = json.loads(mkt.get("clobTokenIds") or "[]")
                outs = [str(o).lower() for o in json.loads(mkt.get("outcomes") or "[]")]
                up_id = dn_id = None
                for i, o in enumerate(outs):
                    if o in ("up", "yes"): up_id = tids[i]
                    elif o in ("down", "no"): dn_id = tids[i]
                if not up_id: up_id = tids[0]
                if not dn_id: dn_id = tids[1]
                return {
                    "condition_id": mkt.get("conditionId"),
                    "question_id": mkt.get("questionID"),
                    "title": mkt.get("question", slug),
                    "up_id": up_id,
                    "down_id": dn_id,
                    "slug": slug
                }
    except Exception:
        pass
    return None

def probe_best_asks(up_id, dn_id):
    def get_ask(tid):
        try:
            r = requests.get(f"{CLOB_HOST}/book", params={"token_id": tid}, timeout=2)
            if r.status_code == 200:
                asks = r.json().get("asks", [])
                if asks:
                    return float(min(asks, key=lambda a: float(a["price"]))["price"])
        except Exception: pass
        return None
    return get_ask(up_id), get_ask(dn_id)

# ── Main Bot Trading Loop ────────────────────────────────────────────────────────
def bot_loop():
    log("[START] Launching Polymarket Chainlink Latency Arbitrage Engine...")
    ws_feed.start()
    time.sleep(2)

    tick = ws_feed.latest()
    if not tick:
        log("[ERROR] Failed to connect to Chainlink WS feed.")
        bot_state["status"] = "Feed Connection Error"
        return

    log(f"[SUCCESS] Connected to Chainlink WS Feed. Spot BTC: ${tick[0]:,.2f}")
    bot_state["status"] = "Active Scanning"

    while True:
        try:
            now = time.time()
            w_s = int(now // WINDOW_SECS) * WINDOW_SECS
            w_e = w_s + WINDOW_SECS
            secs_into = now - w_s
            remaining = w_e - now
            slug = f"btc-updown-5m-{w_s}"
            bot_state["current_slug"] = slug

            if secs_into > 10:
                sleep_secs = remaining + 0.5
                log(f"[WAIT] Started mid-window ({int(secs_into)}s in). Sleeping {int(sleep_secs)}s...")
                time.sleep(max(0, sleep_secs))
                continue

            log(f"--- NEW CYCLE: {slug} ---")
            ptb = None
            for _ in range(100):
                tick = ws_feed.latest()
                if tick and tick[1] >= w_s * 1000:
                    ptb = tick[0]
                    break
                time.sleep(0.1)

            if not ptb:
                tick = ws_feed.latest()
                ptb = tick[0] if tick else 65000.0

            bot_state["ptb"] = ptb
            log(f"[PTB] Price to Beat: ${ptb:,.2f}")

            market = None
            for _ in range(20):
                market = resolve_market_by_slug(slug)
                if market: break
                time.sleep(0.5)

            if not market:
                log(f"[WARN] Market IDs not resolved for {slug}. Sleeping {int(remaining)}s.")
                time.sleep(remaining)
                continue

            last_probe_time = 0
            executed_trade = False

            while True:
                curr_t = time.time()
                t_rem = w_e - curr_t

                if t_rem < 15:
                    break

                if t_rem > 90:
                    time.sleep(0.5)
                    continue

                if executed_trade:
                    time.sleep(1)
                    continue

                tick = ws_feed.latest()
                if not tick:
                    time.sleep(0.1)
                    continue

                btc_price = tick[0]
                diff = btc_price - ptb
                p_up = calculate_true_probability(btc_price, ptb, t_rem, BTC_VOLATILITY)
                p_down = 1.0 - p_up

                if curr_t - last_probe_time >= PROBE_INTERVAL:
                    last_probe_time = curr_t
                    up_ask, down_ask = probe_best_asks(market["up_id"], market["down_id"])

                    if up_ask is not None and down_ask is not None:
                        edge_up = p_up - up_ask
                        edge_dn = p_down - down_ask

                        log(f"🔎 [PROBE T-{t_rem:.0f}s] Move: ${diff:+.2f} | UP Ask: ${up_ask:.2f} (Edge: {edge_up*100:+.1f}%) | DN Ask: ${down_ask:.2f} (Edge: {edge_dn*100:+.1f}%)")

                        if abs(diff) < MIN_BTC_MOVE:
                            time.sleep(0.1)
                            continue

                        # Signal check UP
                        if edge_up >= MIN_EDGE and MIN_ASK_PRICE <= up_ask <= MAX_ASK_PRICE:
                            executed_trade = True
                            bot_state["total_trades"] += 1
                            sig_msg = f"UP @ ${up_ask:.4f} (Edge: +{edge_up*100:.1f}%, Move: ${diff:+.2f})"
                            bot_state["last_signal"] = sig_msg
                            log(f"🎯 [SIGNAL] {sig_msg}")

                            if POLYMARKET_LIVE_TRADING and clob_client is not None:
                                try:
                                    from py_clob_client.order_builder.constants import BUY
                                    from py_clob_client.clob_types import OrderArgs
                                    resp = clob_client.create_and_post_order(
                                        OrderArgs(token_id=market["up_id"], price=up_ask, size=5.0, side=BUY)
                                    )
                                    order_id = resp.get("orderID", "N/A")
                                    log(f"✅ [LIVE FILL] 5 shares UP @ ${up_ask:.4f} (Total: ${5.0*up_ask:.2f}) | Order ID: {order_id}")
                                    bot_state["history"].append({
                                        "time": datetime.datetime.now(datetime.UTC).strftime("%H:%M:%S"),
                                        "side": "UP",
                                        "price": up_ask,
                                        "cost": 5.0 * up_ask,
                                        "order_id": order_id
                                    })
                                except Exception as e:
                                    log(f"❌ [ORDER ERROR] {e}")

                        # Signal check DOWN
                        elif edge_dn >= MIN_EDGE and MIN_ASK_PRICE <= down_ask <= MAX_ASK_PRICE:
                            executed_trade = True
                            bot_state["total_trades"] += 1
                            sig_msg = f"DOWN @ ${down_ask:.4f} (Edge: +{edge_dn*100:.1f}%, Move: ${diff:+.2f})"
                            bot_state["last_signal"] = sig_msg
                            log(f"🎯 [SIGNAL] {sig_msg}")

                            if POLYMARKET_LIVE_TRADING and clob_client is not None:
                                try:
                                    from py_clob_client.order_builder.constants import BUY
                                    from py_clob_client.clob_types import OrderArgs
                                    resp = clob_client.create_and_post_order(
                                        OrderArgs(token_id=market["down_id"], price=down_ask, size=5.0, side=BUY)
                                    )
                                    order_id = resp.get("orderID", "N/A")
                                    log(f"✅ [LIVE FILL] 5 shares DOWN @ ${down_ask:.4f} (Total: ${5.0*down_ask:.2f}) | Order ID: {order_id}")
                                    bot_state["history"].append({
                                        "time": datetime.datetime.now(datetime.UTC).strftime("%H:%M:%S"),
                                        "side": "DOWN",
                                        "price": down_ask,
                                        "cost": 5.0 * down_ask,
                                        "order_id": order_id
                                    })
                                except Exception as e:
                                    log(f"❌ [ORDER ERROR] {e}")

                time.sleep(0.1)

        except Exception as e:
            log(f"[WARN] Exception in cycle loop: {e}")
            time.sleep(5)

# ── Flask Web Routes ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/status")
def status():
    return jsonify(bot_state)

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "service": "latency-arb-bot"}), 200

# Start bot background thread upon app startup
bot_thread = threading.Thread(target=bot_loop, daemon=True)
bot_thread.start()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
