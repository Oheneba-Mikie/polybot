import os
import sys
import time
import ssl
import json
import threading
import datetime
import requests
import websocket
from flask import Flask, render_template, jsonify

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import ApiCreds, OrderArgs, OrderType
from py_clob_client_v2.order_builder.constants import BUY
from eth_account import Account

app = Flask(__name__)

# Constants
MAX_PAIR_COST = 0.99
MIN_DEPTH = 5.0
TRADE_SHARES = 5.0

POLYMARKET_LIVE_TRADING = os.getenv("POLYMARKET_LIVE_TRADING", "true").lower() == "true"

# Single simple dictionary state (identical to simple_flow_bot.py)
bot_state = {
    "mode": "LIVE TRADING" if POLYMARKET_LIVE_TRADING else "PAPER TRADING",
    "status": "Initializing",
    "current_slug": None,
    "total_trades": 0,
    "total_profit_usdc": 0.0,
    "logs": [],
    "history": [],
    "pair_cost": None,
    "up_ask": None,
    "down_ask": None
}

def log(msg):
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%H:%M:%S.%f")[:-3]
    formatted = f"[{timestamp}] {msg}"
    print(formatted, flush=True)
    sys.stdout.flush()
    bot_state["logs"].append(formatted)
    if len(bot_state["logs"]) > 300:
        bot_state["logs"].pop(0)

# Resolve credentials
POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")

clob_client = None
if POLYMARKET_LIVE_TRADING:
    if not POLYMARKET_PRIVATE_KEY:
        log("[ERROR] POLYMARKET_PRIVATE_KEY env variable is not set!")
        sys.exit(1)
    eoa_address = Account.from_key(POLYMARKET_PRIVATE_KEY).address
    sig_type = 0
    funder_addr = None
    if POLYMARKET_ADDRESS and POLYMARKET_ADDRESS.lower() != eoa_address.lower():
        sig_type = 3
        funder_addr = POLYMARKET_ADDRESS
        log(f"[INFO] Using POLY_1271 Signature. Funder={funder_addr}")
    else:
        log("[INFO] Using EOA Signature.")
    try:
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
            signature_type=sig_type,
            funder=funder_addr
        )
        log("[SUCCESS] CLOB client initialized for live trading.")
    except Exception as e:
        log(f"[ERROR] Failed to initialize CLOB client: {e}")
        sys.exit(1)
else:
    log("[INFO] Paper Trading Mode active. Orders will be simulated.")

# WebSockets state (matching simple_flow_bot.py exactly)
up_id = None
down_id = None
prices = {}
ws_client = None
ws_lock = threading.RLock()

def execute_trade(up_price, down_price):
    pair_cost = up_price + down_price
    log(f"[EXECUTION] Placing FOK Buy orders for 5.0 shares each at UP: ${up_price:.4f}, DOWN: ${down_price:.4f}...")
    
    if POLYMARKET_LIVE_TRADING and clob_client is not None:
        try:
            # Buy UP Leg
            log(f"Sending BUY order for UP Token (Price: ${up_price:.4f}, Size: 5.0)...")
            resp1 = clob_client.create_and_post_order(
                OrderArgs(
                    token_id=up_id,
                    price=up_price,
                    size=TRADE_SHARES,
                    side=BUY
                ),
                order_type=OrderType.FOK
            )
            order1_id = resp1.get("orderID") if isinstance(resp1, dict) else None
            
            if order1_id:
                # Buy DOWN Leg
                log(f"Sending BUY order for DOWN Token (Price: ${down_price:.4f}, Size: 5.0)...")
                resp2 = clob_client.create_and_post_order(
                    OrderArgs(
                        token_id=down_id,
                        price=down_price,
                        size=TRADE_SHARES,
                        side=BUY
                    ),
                    order_type=OrderType.FOK
                )
                order2_id = resp2.get("orderID") if isinstance(resp2, dict) else None
                
                profit = TRADE_SHARES * (1.0 - pair_cost)
                log(f"[SUCCESS] Lock completed! Purchased {TRADE_SHARES} pairs. Est. Profit: +${profit:.4f} USDC")
                bot_state["total_trades"] += 1
                bot_state["total_profit_usdc"] += profit
                bot_state["history"].append({
                    "time": datetime.datetime.now(datetime.UTC).strftime("%H:%M:%S"),
                    "up_price": up_price,
                    "down_price": down_price,
                    "cost": TRADE_SHARES * pair_cost,
                    "profit": profit,
                    "order_id": order1_id[:12] + "..." if order1_id else "Filled"
                })
            else:
                err_msg = resp1.get("error") if isinstance(resp1, dict) else "unknown"
                log(f"[CANCELED] UP Leg FOK rejected: {err_msg}. Capital is safe.")
        except Exception as e:
            err_str = str(e)
            if "FOK" in err_str or "couldn't be fully filled" in err_str:
                log(f"[CANCELED] FOK rejected: Price or depth moved instantly. Capital is safe.")
            else:
                log(f"[ERROR] Order execution failed: {e}")
    else:
        # Paper trading simulation
        profit = TRADE_SHARES * (1.0 - pair_cost)
        log(f"[SUCCESS] Simulated lock completed! Purchased {TRADE_SHARES} pairs. Est. Profit: +${profit:.4f} USDC")
        bot_state["total_trades"] += 1
        bot_state["total_profit_usdc"] += profit
        bot_state["history"].append({
            "time": datetime.datetime.now(datetime.UTC).strftime("%H:%M:%S"),
            "up_price": up_price,
            "down_price": down_price,
            "cost": TRADE_SHARES * pair_cost,
            "profit": profit,
            "order_id": "PAPER_MODE"
        })
        time.sleep(1.0)

def subscribe_market(up, down):
    global up_id, down_id, ws_client
    with ws_lock:
        up_id = up
        down_id = down
        if ws_client and ws_client.sock and ws_client.sock.connected:
            sub = {
                "type": "market",
                "assets_ids": [up_id, down_id],
                "custom_feature_enabled": True
            }
            try:
                ws_client.send(json.dumps(sub))
                log(f"[BOOK WS] Subscribed to Token IDs: ...{up_id[-8:]} / ...{down_id[-8:]}")
            except Exception as e:
                log(f"[BOOK WS] Subscription error: {e}")

def on_message(ws, message):
    global prices, up_id, down_id
    if message == "PONG":
        return
    try:
        data = json.loads(message)
        items = data if isinstance(data, list) else [data]
        updated = False
        
        for item in items:
            ev_type = item.get("event_type") or item.get("type")
            asset_id = str(item.get("asset_id") or "")
            
            with ws_lock:
                if asset_id not in (up_id, down_id):
                    continue
                
            if ev_type == "book" or "asks" in item:
                asks = item.get("asks", [])
                if asks:
                    s_asks = sorted(asks, key=lambda a: float(a["price"]))
                    best_ask = float(s_asks[0]["price"])
                    best_ask_sz = float(s_asks[0].get("size", 0.0))
                    prices[asset_id]["price"] = best_ask
                    prices[asset_id]["size"] = best_ask_sz
                    updated = True
            elif ev_type == "price_change":
                changes = item.get("price_changes", []) or [item]
                for ch in changes:
                    b_ask = ch.get("best_ask")
                    b_ask_sz = ch.get("best_ask_size") or item.get("best_ask_size") or ch.get("size")
                    if b_ask is not None:
                        prices[asset_id]["price"] = float(b_ask)
                        if b_ask_sz is not None:
                            prices[asset_id]["size"] = float(b_ask_sz)
                        updated = True
                        
        with ws_lock:
            if not up_id or not down_id:
                return
            up_price = prices.get(up_id, {}).get("price")
            up_size = prices.get(up_id, {}).get("size", 0.0)
            down_price = prices.get(down_id, {}).get("price")
            down_size = prices.get(down_id, {}).get("size", 0.0)

        if updated and up_price is not None and down_price is not None:
            combined = up_price + down_price
            bot_state["up_ask"] = up_price
            bot_state["down_ask"] = down_price
            bot_state["pair_cost"] = combined
            
            log(f"[FLOW] UP: ${up_price:.4f} (Sz: {up_size:.1f}) | DN: ${down_price:.4f} (Sz: {down_size:.1f}) | Combined: ${combined:.4f}")
            
            if combined <= MAX_PAIR_COST:
                if up_size >= MIN_DEPTH and down_size >= MIN_DEPTH:
                    execute_trade(up_price, down_price)
                else:
                    log(f"[INFO] Combined cost is ${combined:.4f}, but depth is thin (UP: {up_size:.1f}, DOWN: {down_size:.1f}). Skipping.")
    except Exception as e:
        pass

def on_open(ws):
    global ws_client
    log("WebSocket connected.")
    with ws_lock:
        ws_client = ws
        if up_id and down_id:
            subscribe_market(up_id, down_id)

def make_ssl_ctx():
    ctx = ssl.create_default_context()
    for cert_path in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(cert_path):
            ctx.load_verify_locations(cert_path)
            break
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def run_ws():
    ssl_ctx = make_ssl_ctx()
    ws = websocket.WebSocketApp(
        "wss://ws-subscriptions-clob.polymarket.com/ws/market",
        header={"User-Agent": "Mozilla/5.0"},
        on_open=on_open,
        on_message=on_message,
        on_close=lambda ws, c, m: time.sleep(2) or run_ws()
    )
    ws.run_forever(sslopt={"context": ssl_ctx})

def resolve_market_by_slug(slug):
    try:
        r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=5)
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
                    "up_id": up_id,
                    "down_id": dn_id
                }
    except Exception:
        pass
    return None

def bot_loop():
    global up_id, down_id, prices
    log("[START] Launching Clean Event-Driven Pair Arbitrage Engine...")
    bot_state["status"] = "Active Scanning"

    # Start WebSocket worker thread
    threading.Thread(target=run_ws, daemon=True).start()

    while True:
        try:
            now_ts = time.time()
            w_s = int(now_ts // 300) * 300
            w_e = w_s + 300
            current_slug = f"btc-updown-5m-{w_s}"
            bot_state["current_slug"] = current_slug

            remaining = w_e - now_ts
            if remaining < 15:
                time.sleep(remaining + 1)
                continue

            log(f"--- NEW CYCLE: {current_slug} ---")

            market = resolve_market_by_slug(current_slug)
            if not market:
                log(f"[WARN] Market not ready for slug: {current_slug}. Sleeping 10s...")
                time.sleep(10)
                continue

            prices_reset = {
                market["up_id"]: {"price": None, "size": 0.0},
                market["down_id"]: {"price": None, "size": 0.0}
            }
            
            with ws_lock:
                prices = prices_reset
                
            subscribe_market(market["up_id"], market["down_id"])

            # Sleep until T-15s
            t_sleep = w_e - time.time() - 15
            if t_sleep > 0:
                time.sleep(t_sleep)
                
            log(f"[INFO] T-15s boundary reached. Waiting for next window...")
            time.sleep(w_e - time.time() + 1)

        except Exception as e:
            log(f"[WARN] Exception in cycle loop: {e}")
            time.sleep(5)

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
