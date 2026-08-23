import os
import sys
import time
import json
import threading
import datetime
import requests
import websocket
from flask import Flask, jsonify, render_template_string
from dotenv import load_dotenv

load_dotenv()

# App Configuration & Credentials
POLYMARKET_PRIVATE_KEY = os.environ.get("POLYMARKET_PRIVATE_KEY")
POLYMARKET_ADDRESS = os.environ.get("POLYMARKET_ADDRESS")
POLYMARKET_API_KEY = os.environ.get("POLYMARKET_API_KEY")
POLYMARKET_API_SECRET = os.environ.get("POLYMARKET_API_SECRET")
POLYMARKET_API_PASSPHRASE = os.environ.get("POLYMARKET_API_PASSPHRASE")

MAX_TEST_SHARES = 1 # Strictly 1 share per trade ($0.97 - $0.99)
TEST_BUDGET_CAP = 1.00 # Max $1.00 budget per candle

# Global State
state = {
    "bot_name": "PolyMirror (Dying-Side Inverter)",
    "status": "INITIALIZING",
    "current_slug": None,
    "seconds_left": 0,
    "up_id": None,
    "down_id": None,
    "up_ask": 0.0,
    "down_ask": 0.0,
    "trades": [],
    "total_wins": 0,
    "total_losses": 0,
    "total_trades": 0,
    "logs": []
}

state_lock = threading.Lock()
order_books = {}
cycle_traded = False
ws_lock = threading.Lock()

def log(msg):
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    entry = f"[{now_str}] {msg}"
    print(entry, flush=True)
    with state_lock:
        state["logs"].append(entry)
        if len(state["logs"]) > 200:
            state["logs"].pop(0)

# Initialize CLOB Client
clob_client = None
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds, OrderArgs
    from py_clob_client.order_builder.constants import BUY
    
    creds = ApiCreds(
        api_key=POLYMARKET_API_KEY,
        api_secret=POLYMARKET_API_SECRET,
        api_passphrase=POLYMARKET_API_PASSPHRASE
    )
    clob_client = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        key=POLYMARKET_PRIVATE_KEY,
        creds=creds,
        signature_type=2,
        funder=POLYMARKET_ADDRESS
    )
    log(f"[AUTH] Successfully authenticated with Polymarket CLOB. Proxy: {POLYMARKET_ADDRESS}")
except Exception as e:
    log(f"[AUTH ERROR] Failed to initialize CLOB client: {e}")

def execute_opposite_trade(trigger_side, target_side, token_id, ask_price, ask_size):
    global cycle_traded
    if cycle_traded:
        return
    
    cycle_traded = True
    shares_to_buy = min(MAX_TEST_SHARES, max(1, int(ask_size)))
    cost = shares_to_buy * ask_price
    
    log("=" * 70)
    log(f"⚡ [OPPOSITE TRIGGER] Detected Losing Side ({trigger_side} <= 0.05)!")
    log(f"🎯 [OPPOSITE BUY] Staking ON OPPOSITE WINNER ({target_side}) -> {shares_to_buy} shares @ ${ask_price:.2f} (Total Cost: ${cost:.2f})")
    log("=" * 70)
    
    trade_record = {
        "time": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "trigger_side": trigger_side,
        "bought_side": target_side,
        "shares": shares_to_buy,
        "price": ask_price,
        "cost": cost,
        "status": "SUBMITTING",
        "order_id": None
    }
    
    if clob_client:
        try:
            buy_args = OrderArgs(
                price=ask_price,
                size=float(shares_to_buy),
                side=BUY,
                token_id=token_id
            )
            res = clob_client.create_and_post_order(buy_args)
            log(f"✅ [SUCCESS] Order Placed! Response: {res}")
            trade_record["status"] = "FILLED"
            trade_record["order_id"] = str(res.get("orderID", "FILLED"))
        except Exception as e:
            log(f"❌ [ORDER ERROR] {e}")
            trade_record["status"] = f"ERROR: {e}"
    else:
        log(f"📝 [SIMULATED] Would have bought {shares_to_buy} of {target_side} @ ${ask_price:.2f}")
        trade_record["status"] = "SIMULATED"
        
    with state_lock:
        state["trades"].append(trade_record)
        state["total_trades"] += 1

# Background Continuous Scanner Loop with Direct REST Fallback
def scan_loop():
    global cycle_traded, order_books
    last_log_sec = None
    headers = {"User-Agent": "Mozilla/5.0"}
    
    while True:
        try:
            now_ts = time.time()
            w_start = int(now_ts // 300) * 300
            w_end = w_start + 300
            seconds_left = int(w_end - now_ts)
            
            with state_lock:
                state["seconds_left"] = seconds_left
                up_id = state.get("up_id")
                down_id = state.get("down_id")
            
            if up_id and down_id:
                min_up_ask = None
                min_up_sz = 1
                min_down_ask = None
                min_down_sz = 1
                
                # Fetch instant REST order book during the final 20 seconds
                if seconds_left <= 20 and not cycle_traded:
                    try:
                        r_up = requests.get(f"https://clob.polymarket.com/book?token_id={up_id}", headers=headers, timeout=1.5).json()
                        r_dn = requests.get(f"https://clob.polymarket.com/book?token_id={down_id}", headers=headers, timeout=1.5).json()
                        
                        up_asks_list = r_up.get("asks", [])
                        if up_asks_list:
                            min_up_ask = min([float(x["price"]) for x in up_asks_list])
                            min_up_sz = float([x["size"] for x in up_asks_list if float(x["price"]) == min_up_ask][0])
                            
                        dn_asks_list = r_dn.get("asks", [])
                        if dn_asks_list:
                            min_down_ask = min([float(x["price"]) for x in dn_asks_list])
                            min_down_sz = float([x["size"] for x in dn_asks_list if float(x["price"]) == min_down_ask][0])
                    except Exception:
                        pass
                
                # Fallback to WebSocket cache
                if min_up_ask is None or min_down_ask is None:
                    with ws_lock:
                        up_asks = order_books.get(up_id, {}).get("asks", {})
                        down_asks = order_books.get(down_id, {}).get("asks", {})
                        if up_asks:
                            min_up_ask = min(up_asks.keys())
                            min_up_sz = up_asks[min_up_ask]
                        if down_asks:
                            min_down_ask = min(down_asks.keys())
                            min_down_sz = down_asks[min_down_ask]
                            
                with state_lock:
                    if min_up_ask is not None:
                        state["up_ask"] = min_up_ask
                    if min_down_ask is not None:
                        state["down_ask"] = min_down_ask
                
                # Log status in the final 25 seconds
                if seconds_left <= 25 and seconds_left != last_log_sec and min_up_ask is not None and min_down_ask is not None:
                    last_log_sec = seconds_left
                    log(f"[SCAN {seconds_left}s left] UP: ${min_up_ask:.4f} | DN: ${min_down_ask:.4f} | Traded: {cycle_traded}")
                
                # THE OPPOSITE STAKING TRIGGER IN THE FINAL 15 SECONDS:
                if 1 <= seconds_left <= 15 and not cycle_traded:
                    if min_up_ask is not None and min_up_ask <= 0.05 and min_down_ask is not None and min_down_ask >= 0.90:
                        execute_opposite_trade("UP", "DOWN", down_id, min_down_ask, min_down_sz)
                    elif min_down_ask is not None and min_down_ask <= 0.05 and min_up_ask is not None and min_up_ask >= 0.90:
                        execute_opposite_trade("DOWN", "UP", up_id, min_up_ask, min_up_sz)
                        
        except Exception as e:
            log(f"[SCAN EXCEPTION] {e}")
            
        time.sleep(0.3)

# WebSocket Feed Handler
def on_message(ws, message):
    global order_books
    if message == "PONG":
        return
    try:
        data = json.loads(message)
        items = data if isinstance(data, list) else [data]
        with ws_lock:
            for item in items:
                asset_id = item.get("asset_id")
                if not asset_id:
                    continue
                if asset_id not in order_books:
                    order_books[asset_id] = {"asks": {}, "bids": {}}
                    
                price_flt = float(item.get("price", 0))
                size_flt = float(item.get("size", 0))
                side = item.get("side", "").upper()
                
                if side == "SELL":
                    if size_flt <= 0:
                        order_books[asset_id]["asks"].pop(price_flt, None)
                    else:
                        order_books[asset_id]["asks"][price_flt] = size_flt
                elif side == "BUY":
                    if size_flt <= 0:
                        order_books[asset_id]["bids"].pop(price_flt, None)
                    else:
                        order_books[asset_id]["bids"][price_flt] = size_flt
    except Exception:
        pass

def on_open(ws):
    log("[WS] Connected to CLOB WebSocket feed.")

def ws_thread():
    while True:
        try:
            ws = websocket.WebSocketApp(
                "wss://ws-subscriptions-clob.polymarket.com/ws/market",
                on_open=on_open,
                on_message=on_message
            )
            ws.run_forever(ping_interval=10, ping_timeout=5)
        except Exception:
            time.sleep(1)

# Main Cycle Synchronizer
def main_bot_loop():
    global cycle_traded, order_books
    current_cycle_id = None
    headers = {"User-Agent": "Mozilla/5.0"}
    
    log("[BOT] PolyMirror bot initialized and starting cycle sync...")
    with state_lock:
        state["status"] = "RUNNING"
        
    threading.Thread(target=ws_thread, daemon=True).start()
    threading.Thread(target=scan_loop, daemon=True).start()
    
    while True:
        try:
            now_ts = time.time()
            w_start = int(now_ts // 300) * 300
            
            if current_cycle_id != w_start:
                current_cycle_id = w_start
                cycle_traded = False
                
                slug = f"btc-updown-5m-{w_start}"
                log(f"\n==================== NEW 5M CANDLE: {slug} ====================")
                
                with state_lock:
                    state["current_slug"] = slug
                
                try:
                    r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", headers=headers, timeout=5).json()
                    if r:
                        m = r[0]["markets"][0]
                        tokens = eval(m["clobTokenIds"])
                        up_id = tokens[0]
                        down_id = tokens[1]
                        
                        with state_lock:
                            state["up_id"] = up_id
                            state["down_id"] = down_id
                            
                        log(f"[SYNC] Subscribed Token IDs: UP: ...{up_id[-8:]} | DOWN: ...{down_id[-8:]}")
                        
                        r_up = requests.get(f"https://clob.polymarket.com/book?token_id={up_id}", headers=headers, timeout=3).json()
                        r_dn = requests.get(f"https://clob.polymarket.com/book?token_id={down_id}", headers=headers, timeout=3).json()
                        
                        with ws_lock:
                            order_books[up_id] = {"asks": {float(x["price"]): float(x["size"]) for x in r_up.get("asks", [])}, "bids": {float(x["price"]): float(x["size"]) for x in r_up.get("bids", [])}}
                            order_books[down_id] = {"asks": {float(x["price"]): float(x["size"]) for x in r_dn.get("asks", [])}, "bids": {float(x["price"]): float(x["size"]) for x in r_dn.get("bids", [])}}
                            
                        log("[SYNC] Initial REST order book snapshots primed.")
                except Exception as e:
                    log(f"[SYNC ERROR] {e}")
                    
        except Exception as e:
            log(f"[LOOP EXCEPTION] {e}")
            
        time.sleep(1)

# Start Bot in Daemon Thread
threading.Thread(target=main_bot_loop, daemon=True).start()

# Flask Web Dashboard for Railway Monitoring
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>PolyMirror Bot Status</title>
    <meta http-equiv="refresh" content="3">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
        .container { max-width: 900px; margin: auto; background: #1e293b; padding: 25px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        h1 { color: #38bdf8; margin-top: 0; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .card { background: #334155; padding: 15px; border-radius: 8px; text-align: center; }
        .card .title { font-size: 0.85em; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; }
        .card .value { font-size: 1.5em; font-weight: bold; margin-top: 5px; color: #38bdf8; }
        .badge { display: inline-block; padding: 4px 10px; border-radius: 20px; font-weight: bold; font-size: 0.85em; }
        .badge-green { background: #059669; color: #fff; }
        .log-box { background: #020617; border: 1px solid #334155; border-radius: 8px; padding: 15px; height: 300px; overflow-y: auto; font-family: monospace; font-size: 0.85em; color: #a5f3fc; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #334155; }
        th { background: #0f172a; color: #94a3b8; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🪞 PolyMirror Bot Dashboard</h1>
        <div class="grid">
            <div class="card">
                <div class="title">Status</div>
                <div class="value"><span class="badge badge-green">{{ state.status }}</span></div>
            </div>
            <div class="card">
                <div class="title">Current Candle</div>
                <div class="value" style="font-size: 1em;">{{ state.current_slug or 'Syncing...' }}</div>
            </div>
            <div class="card">
                <div class="title">Time Left</div>
                <div class="value">{{ state.seconds_left }}s</div>
            </div>
            <div class="card">
                <div class="title">UP Ask / DOWN Ask</div>
                <div class="value">${{ "%.2f"|format(state.up_ask) }} / ${{ "%.2f"|format(state.down_ask) }}</div>
            </div>
        </div>

        <h3>Recent Trades</h3>
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Trigger (Dying Side)</th>
                    <th>Bought Outcome</th>
                    <th>Shares</th>
                    <th>Price</th>
                    <th>Cost</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {% for t in state.trades[-5:]|reverse %}
                <tr>
                    <td>{{ t.time }}</td>
                    <td><span style="color: #ef4444; font-weight: bold;">{{ t.trigger_side }} (<= 0.05)</span></td>
                    <td><span style="color: #22c55e; font-weight: bold;">{{ t.bought_side }}</span></td>
                    <td>{{ t.shares }}</td>
                    <td>${{ "%.2f"|format(t.price) }}</td>
                    <td>${{ "%.2f"|format(t.cost) }}</td>
                    <td>{{ t.status }}</td>
                </tr>
                {% else %}
                <tr><td colspan="7" style="text-align: center; color: #64748b;">No trades executed yet. Monitoring live 15s windows...</td></tr>
                {% endfor %}
            </tbody>
        </table>

        <h3>Live Scanner Activity</h3>
        <div class="log-box">
            {% for l in state.logs|reverse %}
            <div>{{ l }}</div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    with state_lock:
        return render_template_string(HTML_TEMPLATE, state=state)

@app.route("/api/state")
def get_state():
    with state_lock:
        return jsonify(state)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
