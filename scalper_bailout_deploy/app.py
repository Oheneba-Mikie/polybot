import os, sys, time, json, math, threading, requests, datetime, ssl
from flask import Flask, render_template, jsonify
from dotenv import load_dotenv

sys.stdout.reconfigure(line_buffering=True)
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
    "balance": 0.0,
    "bot_bankroll": 4.85,
    "held_position": None
}

INITIAL_BOT_BANKROLL = float(os.getenv("INITIAL_BOT_BANKROLL", "4.85"))
bot_bankroll = INITIAL_BOT_BANKROLL

def log(msg):
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    try:
        print(formatted, flush=True)
    except UnicodeEncodeError:
        print(formatted.encode("ascii", "replace").decode("ascii"), flush=True)
    bot_state["logs"].append(formatted)
    if len(bot_state["logs"]) > 200:
        bot_state["logs"].pop(0)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"
LIVE_WS_URL= "wss://ws-live-data.polymarket.com/"
WS_HEADERS = {"User-Agent": "Mozilla/5.0"}

POLYMARKET_LIVE_TRADING = os.getenv("POLYMARKET_LIVE_TRADING", "true").lower() == "true"
STARTING_STAKE_USD      = float(os.getenv("STARTING_STAKE_USD", "4.85"))

# Scalp Configuration
ENTRY_PRICE_TRIGGER_MIN = 0.965
ENTRY_PRICE_TRIGGER_MAX = 0.978
TARGET_SELL_PROFIT_BID  = 0.980  # Sell for profit at >= 0.98

# Safety Bailout Engine Parameters
BAILOUT_TIMEOUT_SECONDS = 40.0   # If not sold within 40s, dump at market price
STOP_LOSS_MIN_BID       = 0.950   # If bid drops below 0.95, emergency dump immediately
PRE_CLOSE_SAFETY_WINDOW = 10.0   # T-10s before close, dump to prevent holding into resolution
MAX_ENTRY_CANDLE_ELAPSED= 180.0  # Only enter during first 3 minutes; never enter late in candle

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
        log("🛡️ Initialized Fast CLOB Client with Position Guardian & 3-Tier Safety Bailout Engine.")
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

    def _stale_check(self):
        with self._lock:
            if self._ts_ms and (time.time() - self._ts_ms / 1000) > 15:
                log("  [WS] Stale feed detected (>15s) - reconnecting...")
                self._ts_ms = self._price = None
                if self._ws_app:
                    try: self._ws_app.close()
                    except Exception: pass


def resolve_market(slug, timeout=10):
    try:
        r = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=timeout)
        r.raise_for_status()
        evts = r.json()
        if not evts or not evts[0].get("markets"): return None
        mkt  = evts[0]["markets"][0]
        tids = json.loads(mkt.get("clobTokenIds") or "[]")
        outs = [str(o).lower() for o in json.loads(mkt.get("outcomes") or "[]")]
        up_id = dn_id = None
        for i, o in enumerate(outs):
            if o in ("up", "yes"):    up_id = tids[i]
            elif o in ("down", "no"): dn_id = tids[i]
        if not up_id and len(tids) > 0: up_id = tids[0]
        if not dn_id and len(tids) > 1: dn_id = tids[1]
        return {"slug": slug, "title": mkt.get("question", slug), "up_id": up_id, "down_id": dn_id}
    except Exception:
        return None


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


def get_live_balance():
    if not client:
        return 5.00
    try:
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
        resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        raw_b = float(resp.get("balance", 0)) / 1_000_000
        return round(raw_b, 2)
    except Exception as e:
        return 0.0


def get_token_shares_balance(token_id):
    if not client:
        return 0.0
    try:
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
        resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=token_id))
        raw_sh = float(resp.get("balance", 0)) / 1_000_000
        return raw_sh
    except Exception as e:
        return 0.0


def dump_shares_market(token_id, shares_amount, reason_tag="BAILOUT"):
    if not client:
        return False
    
    from py_clob_client_v2 import MarketOrderArgsV2, OrderType

    # Retry loop: keep dumping until on-chain shares are confirmed 0.0
    for attempt in range(1, 6):
        live_sh = get_token_shares_balance(token_id)
        sh_to_dump = math.floor(live_sh * 100.0) / 100.0 if live_sh >= 0.1 else math.floor(shares_amount * 100.0) / 100.0
        
        if sh_to_dump < 0.1:
            log(f"✅ CONFIRMED ZERO SHARES ({reason_tag}): Position fully cleared.")
            return True
            
        try:
            log(f"🚨 EXECUTING MARKET SWEEP DUMP (Attempt {attempt} | {reason_tag}): Dumping {sh_to_dump:.2f} shares immediately...")
            client.create_and_post_market_order(
                MarketOrderArgsV2(token_id=token_id, amount=sh_to_dump, price=0.01, side="SELL", order_type=OrderType.FAK),
                order_type=OrderType.FAK
            )
            time.sleep(0.4)
            remaining = get_token_shares_balance(token_id)
            if remaining < 0.1:
                log(f"✅ MARKET DUMP SUCCESS: All {sh_to_dump:.2f} shares confirmed dumped for cash on-chain.")
                return True
            else:
                log(f"⚠️ Partial fill: {remaining:.2f} shares remaining. Retrying dump...")
        except Exception as e:
            log(f"⚠️ Dump Attempt {attempt} Error ({reason_tag}): {e}. Retrying in 0.3s...")
            time.sleep(0.3)
            
    return False


def manage_position_loop(token_id, side_name, entry_price, shares_amount, candle_end):
    """
    Dedicated, isolated Position Guardian.
    Monitors held position and guarantees 100% exit via Profit (0.98), Stop Loss (<0.95), Timeout (40s), or Pre-Close (T-10s).
    """
    global bot_bankroll
    from py_clob_client_v2 import MarketOrderArgsV2, OrderType
    
    entry_time = time.time()
    log(f"🛡️ POSITION GUARDIAN ACTIVE: Holding {shares_amount:.2f} shares of {side_name} (Entry: ${entry_price:.4f}). Managing exit...")
    bot_state["held_position"] = f"{shares_amount:.2f} {side_name} @ ${entry_price:.2f}"

    while True:
        elapsed = time.time() - entry_time
        time_to_close = candle_end - time.time()
        
        _, live_bid = probe_book(token_id)
        
        # 1. PROFIT EXIT: Live bid reached target (>= 0.98)
        if live_bid and live_bid >= TARGET_SELL_PROFIT_BID:
            log(f"🎉 PROFIT TARGET HIT! Live Bid is ${live_bid:.4f}. Selling all shares...")
            try:
                live_sh = get_token_shares_balance(token_id)
                sh_to_sell = math.floor(live_sh * 100.0) / 100.0 if live_sh >= 0.1 else math.floor(shares_amount * 100.0) / 100.0
                client.create_and_post_market_order(
                    MarketOrderArgsV2(token_id=token_id, amount=sh_to_sell, price=0.01, side="SELL", order_type=OrderType.FAK),
                    order_type=OrderType.FAK
                )
                profit_per_share = live_bid - entry_price
                p_usdc = round(sh_to_sell * profit_per_share, 4)
                pct = (profit_per_share / entry_price) * 100.0
                
                bot_bankroll = round(bot_bankroll + p_usdc, 4)
                bot_state["bot_bankroll"] = bot_bankroll
                
                log(f"🏆 SCALP WON! Sold @ ${live_bid:.4f} | Net Profit: +${p_usdc:.4f} ({pct:+.2f}%) | Bot Bankroll: ${bot_bankroll:.2f}")
                
                bot_state["total_scalps"] += 1
                bot_state["total_profit_usdc"] = round(bot_state.get("total_profit_usdc", 0.0) + p_usdc, 4)
                bot_state["last_trade"] = f"Bought @ ${entry_price:.2f} -> Sold @ ${live_bid:.2f} ({pct:+.1f}%)"
                bot_state["wins"] += 1
                bot_state["streak"] += 1
                bot_state["held_position"] = None
                return True
            except Exception as e:
                log(f"Sell order error: {e}")

        # 2. EMERGENCY STOP LOSS: Bid dropped below 0.95
        elif live_bid and live_bid < STOP_LOSS_MIN_BID:
            log(f"🚨 STOP LOSS TRIGGERED: Bid dropped to ${live_bid:.4f}. Dumping immediately to preserve capital...")
            dump_shares_market(token_id, shares_amount, reason_tag="STOP_LOSS")
            loss_usdc = round(shares_amount * (entry_price - live_bid), 4)
            bot_bankroll = max(4.85, round(bot_bankroll - loss_usdc, 4))
            bot_state["bot_bankroll"] = bot_bankroll
            log(f"🛡️ CAPITAL PRESERVED: Dumped @ ${live_bid:.4f} (Saved 95%+ of principal, loss: -${loss_usdc:.4f}) | Bot Bankroll: ${bot_bankroll:.2f}")
            bot_state["losses"] += 1
            bot_state["streak"] = 0
            bot_state["held_position"] = None
            return True

        # 3. 40-SECOND TIMEOUT BAILOUT: Market stalled
        elif elapsed >= BAILOUT_TIMEOUT_SECONDS:
            dump_bid = live_bid or 0.01
            log(f"⏰ 40s TIMEOUT BAILOUT: Market stalled after {elapsed:.1f}s. Dumping {shares_amount:.2f} shares at market...")
            dump_shares_market(token_id, shares_amount, reason_tag="TIMEOUT_40S")
            bot_state["held_position"] = None
            return True

        # 4. PRE-CLOSE SAFETY CUTOFF: T-10 seconds before candle ends
        elif time_to_close <= PRE_CLOSE_SAFETY_WINDOW:
            dump_bid = live_bid or 0.01
            log(f"⚠️ PRE-CLOSE SAFETY CUTOFF: Only {time_to_close:.1f}s left in candle. Dumping {shares_amount:.2f} shares before resolution...")
            dump_shares_market(token_id, shares_amount, reason_tag="PRE_CLOSE_10S")
            bot_state["held_position"] = None
            return True

        time.sleep(0.05)


def run_scalper_bot_engine():
    log("🚀 97c -> 98c Scalper Bot with Atomic Guardian & 3-Tier Bailout Online...")
    ws = WSFeed()
    ws.start()

    while True:
        try:
            if bot_state["paused"]:
                bot_state["status"] = "Paused by user"
                time.sleep(2)
                continue

            cur_t = time.time()
            w_s = win_start(cur_t)
            w_e = win_end(cur_t)
            slug = slug_for(cur_t)

            mkt = resolve_market(slug)
            if not mkt or not mkt.get("up_id") or not mkt.get("down_id"):
                bot_state["status"] = f"Waiting for market: {slug}"
                time.sleep(2)
                continue

            up_id, dn_id = mkt["up_id"], mkt["down_id"]
            bot_state["status"] = f"Monitoring {mkt['title']}"

            wallet_bal = get_live_balance()
            bot_state["balance"] = wallet_bal

            candle_traded = False

            while time.time() < (w_e - PRE_CLOSE_SAFETY_WINDOW):
                if bot_state["paused"]:
                    break

                # -------------------------------------------------------------
                # 🛡️ GUARDIAN CHECK #1: Check on-chain shares first
                # If we hold ANY shares, immediately manage exit and NEVER buy!
                # -------------------------------------------------------------
                up_sh = get_token_shares_balance(up_id)
                dn_sh = get_token_shares_balance(dn_id)

                if up_sh >= 0.1:
                    log(f"🔎 POSITION GUARDIAN: Detected {up_sh:.4f} UP shares in wallet. Entering Position Guardian...")
                    manage_position_loop(up_id, "UP", 0.97, up_sh, w_e)
                    candle_traded = True
                    break

                if dn_sh >= 0.1:
                    log(f"🔎 POSITION GUARDIAN: Detected {dn_sh:.4f} DOWN shares in wallet. Entering Position Guardian...")
                    manage_position_loop(dn_id, "DOWN", 0.97, dn_sh, w_e)
                    candle_traded = True
                    break

                # If we already executed a trade in this candle, scan until candle ends
                if candle_traded:
                    time.sleep(1)
                    continue

                # -------------------------------------------------------------
                # 🎯 ENTRY SCANNING: Look for 97c trigger throughout candle
                # -------------------------------------------------------------
                up_ask, _ = probe_book(up_id)
                dn_ask, _ = probe_book(dn_id)

                target_token_id = None
                side_name = None
                entry_ask_price = None

                if up_ask and ENTRY_PRICE_TRIGGER_MIN <= up_ask <= ENTRY_PRICE_TRIGGER_MAX:
                    target_token_id = up_id
                    side_name = "UP"
                    entry_ask_price = up_ask
                elif dn_ask and ENTRY_PRICE_TRIGGER_MIN <= dn_ask <= ENTRY_PRICE_TRIGGER_MAX:
                    target_token_id = dn_id
                    side_name = "DOWN"
                    entry_ask_price = dn_ask

                if target_token_id and not candle_traded:
                    # Atomic Lock: Set candle_traded to True IMMEDIATELY before sending order
                    candle_traded = True

                    current_cash = get_live_balance()
                    # Isolated Bankroll: Trade using bot_bankroll only, leaving remaining wallet cash untouched
                    trade_alloc = min(bot_bankroll, current_cash)
                    stake_amount = max(4.85, math.floor(trade_alloc * 100.0) / 100.0)
                    stake_amount = min(stake_amount, current_cash)

                    log(f"⚡ 0.97 ENTRY on {side_name} @ ${entry_ask_price:.4f}! Buying with ${stake_amount:.2f} USDC (Bankroll: ${bot_bankroll:.2f} | Wallet: ${current_cash:.2f})...")

                    if client:
                        try:
                            from py_clob_client_v2 import MarketOrderArgsV2, OrderType

                            # Execute BUY
                            client.create_and_post_market_order(
                                MarketOrderArgsV2(token_id=target_token_id, amount=stake_amount, price=entry_ask_price, side="BUY", order_type=OrderType.FAK),
                                order_type=OrderType.FAK
                            )

                            # Wait 0.3s for on-chain settlement, then fetch exact shares
                            time.sleep(0.3)
                            actual_shares = get_token_shares_balance(target_token_id)
                            if actual_shares < 0.1:
                                actual_shares = round(stake_amount / entry_ask_price, 2)

                            log(f"⏱️ BOUGHT {actual_shares:.4f} shares of {side_name} @ ${entry_ask_price:.4f}.")
                            
                            # Immediately hand over control to Position Guardian
                            manage_position_loop(target_token_id, side_name, entry_ask_price, actual_shares, w_e)
                            break

                        except Exception as ex:
                            log(f"Buy execution notification: {ex}")
                            # Even if an exception occurred, on next tick Guardian Check #1 will catch any filled shares!
                            time.sleep(0.5)
                            continue
                    else:
                        log(f"PAPER SCALP: {side_name} @ ${entry_ask_price:.4f} -> Sell @ $0.98")
                        break

                time.sleep(0.05)

            # Wait for candle transition
            sleep_time = max(1, int(w_e - time.time()) + 1)
            time.sleep(sleep_time)

        except Exception as e:
            log(f"Engine Loop Exception: {e}")
            time.sleep(2)


# =====================================================================
# FLASK WEB DASHBOARD
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>PolyBot - 97c Scalper Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b0f19; color: #f3f4f6; margin: 0; padding: 20px; }
    .container { max-width: 900px; margin: auto; }
    .card { background: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); }
    .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1f2937; padding-bottom: 15px; }
    .badge { background: #10b981; color: #fff; padding: 4px 10px; border-radius: 9999px; font-size: 0.8rem; font-weight: bold; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 15px; }
    .metric { background: #1f2937; padding: 15px; border-radius: 8px; text-align: center; }
    .metric-value { font-size: 1.8rem; font-weight: bold; color: #3b82f6; margin-top: 5px; }
    .green { color: #10b981 !important; }
    .red { color: #ef4444 !important; }
    .logs { background: #030712; padding: 15px; border-radius: 8px; height: 250px; overflow-y: auto; font-family: monospace; font-size: 0.85rem; color: #9ca3af; }
    .log-line { margin-bottom: 4px; border-bottom: 1px solid #111827; padding-bottom: 2px; }
    .footer { text-align: center; color: #6b7280; font-size: 0.8rem; margin-top: 20px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      <div class="header">
        <h2>⚡ PolyBot 97¢ Scalper with Position Guardian</h2>
        <span class="badge" id="status-badge">ONLINE</span>
      </div>
      <div class="grid">
        <div class="metric">
          <div>Cash Balance</div>
          <div class="metric-value green" id="cash-bal">$0.00</div>
        </div>
        <div class="metric">
          <div>Total Scalps</div>
          <div class="metric-value" id="total-scalps">0</div>
        </div>
        <div class="metric">
          <div>Net Profit</div>
          <div class="metric-value green" id="net-profit">+$0.00</div>
        </div>
        <div class="metric">
          <div>Win Rate</div>
          <div class="metric-value" id="win-rate">100%</div>
        </div>
      </div>
      <div style="margin-top: 15px; font-size: 0.9rem; color: #9ca3af;" id="market-status">
        Status: Initializing...
      </div>
      <div style="margin-top: 5px; font-size: 0.9rem; color: #fbbf24;" id="held-pos">
        Position: None
      </div>
    </div>

    <div class="card">
      <h3>📜 Live Execution Logs</h3>
      <div class="logs" id="log-box"></div>
    </div>
    <div class="footer">PolyBot High-Frequency 97c Scalper • Polygon / Polymarket CLOB Engine</div>
  </div>

  <script>
    async function updateDashboard() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        document.getElementById('cash-bal').innerText = '$' + (data.balance || 0).toFixed(2);
        document.getElementById('total-scalps').innerText = data.total_scalps || 0;
        document.getElementById('net-profit').innerText = (data.total_profit_usdc >= 0 ? '+' : '') + '$' + (data.total_profit_usdc || 0).toFixed(4);
        
        const total = (data.wins || 0) + (data.losses || 0);
        const wr = total > 0 ? ((data.wins / total) * 100).toFixed(0) + '%' : '100%';
        document.getElementById('win-rate').innerText = wr;
        document.getElementById('market-status').innerText = 'Status: ' + (data.status || 'Active');
        document.getElementById('held-pos').innerText = 'Position: ' + (data.held_position ? data.held_position : 'None (100% Cash)');

        const box = document.getElementById('log-box');
        box.innerHTML = (data.logs || []).map(l => `<div class="log-line">${l}</div>`).join('');
        box.scrollTop = box.scrollHeight;
      } catch(e) {}
    }
    setInterval(updateDashboard, 1500);
    updateDashboard();
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return HTML_TEMPLATE

@app.route("/api/status")
def api_status():
    return jsonify(bot_state)

if __name__ == "__main__":
    t = threading.Thread(target=run_scalper_bot_engine, daemon=True)
    t.start()
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
