import os
import sys
import time
import json
import threading
import datetime
import requests
import websocket
from dotenv import load_dotenv

# Add local path
sys.path.append(r"d:\Desktop\antigravity\POLYBOT\polybot\latency_arb_railway_deploy")

load_dotenv(r"d:\Desktop\antigravity\POLYBOT\polybot\.env")

POLYMARKET_PRIVATE_KEY = os.environ.get("POLYMARKET_PRIVATE_KEY")
POLYMARKET_ADDRESS = os.environ.get("POLYMARKET_ADDRESS")
POLYMARKET_API_KEY = os.environ.get("POLYMARKET_API_KEY")
POLYMARKET_API_SECRET = os.environ.get("POLYMARKET_API_SECRET")
POLYMARKET_API_PASSPHRASE = os.environ.get("POLYMARKET_API_PASSPHRASE")

MAX_TEST_SHARES = 1 # HARD CAP: 1 share ($0.97 - $0.99)
TEST_BUDGET_CAP = 1.00 # Max $1.00 spend

print("=" * 80)
print(f"LOCAL EXPERIMENT: OPPOSITE STAKING TRIGGER (MAX SPEND: ${TEST_BUDGET_CAP:.2f})")
print("=" * 80)

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
    print(f"[AUTH] Authenticated with Polymarket CLOB. Proxy: {POLYMARKET_ADDRESS}")
except Exception as e:
    print(f"[AUTH ERROR] {e}")

up_id = None
down_id = None
current_slug = None
order_books = {}
cycle_traded = False
ws_lock = threading.Lock()

def log(msg):
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    print(f"[{now_str}] {msg}", flush=True)

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
    
    if clob_client:
        try:
            buy_args = OrderArgs(
                price=ask_price,
                size=float(shares_to_buy),
                side=BUY,
                token_id=token_id
            )
            res = clob_client.create_and_post_order(buy_args)
            log(f"✅ [SUCCESS] Local Test Order Placed! Response: {res}")
        except Exception as e:
            log(f"❌ [ORDER ERROR] {e}")
    else:
        log(f"📝 [SIMULATED] Would have bought {shares_to_buy} of {target_side} @ ${ask_price:.2f}")

# Dedicated Scanning Loop with Direct REST Fallback
def scan_loop():
    global cycle_traded, up_id, down_id, order_books
    last_log_sec = None
    headers = {"User-Agent": "Mozilla/5.0"}
    
    while True:
        try:
            now_ts = time.time()
            w_start = int(now_ts // 300) * 300
            w_end = w_start + 300
            seconds_left = int(w_end - now_ts)
            
            if up_id and down_id:
                min_up_ask = None
                min_up_sz = 1
                min_down_ask = None
                min_down_sz = 1
                
                # If we're in the final 20 seconds, fetch an immediate REST book snapshot
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
                    except Exception as e:
                        pass
                
                # Otherwise read from WebSocket cache
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
                
                # Log status in final 25 seconds
                if seconds_left <= 25 and seconds_left != last_log_sec and min_up_ask is not None and min_down_ask is not None:
                    last_log_sec = seconds_left
                    log(f"[SCAN {seconds_left}s left] UP: ${min_up_ask:.4f} | DN: ${min_down_ask:.4f} | Traded: {cycle_traded}")
                
                # THE OPPOSITE STAKING TRIGGER IN THE FINAL 15 SECONDS:
                if 1 <= seconds_left <= 15 and not cycle_traded:
                    # If UP is dying (<= 0.05), buy the OPPOSITE (DOWN)!
                    if min_up_ask is not None and min_up_ask <= 0.05 and min_down_ask is not None and min_down_ask >= 0.90:
                        execute_opposite_trade("UP", "DOWN", down_id, min_down_ask, min_down_sz)
                    # If DOWN is dying (<= 0.05), buy the OPPOSITE (UP)!
                    elif min_down_ask is not None and min_down_ask <= 0.05 and min_up_ask is not None and min_up_ask >= 0.90:
                        execute_opposite_trade("DOWN", "UP", up_id, min_up_ask, min_up_sz)
        except Exception as e:
            log(f"[SCAN EXCEPTION] {e}")
            
        time.sleep(0.3)

threading.Thread(target=scan_loop, daemon=True).start()

# WebSocket Message Handler
def on_message(ws, message):
    global up_id, down_id, order_books
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
    log("[WS] Connected to CLOB WebSocket.")

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

threading.Thread(target=ws_thread, daemon=True).start()

# Main Loop: Sync 5m Candle Slug
current_cycle_id = None
while True:
    now_ts = time.time()
    w_start = int(now_ts // 300) * 300
    
    if current_cycle_id != w_start:
        current_cycle_id = w_start
        cycle_traded = False
        
        current_slug = f"btc-updown-5m-{w_start}"
        log(f"\n==================== NEW 5M CANDLE: {current_slug} ====================")
        
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(f"https://gamma-api.polymarket.com/events?slug={current_slug}", headers=headers, timeout=5).json()
            if r:
                m = r[0]["markets"][0]
                tokens = eval(m["clobTokenIds"])
                up_id = tokens[0]
                down_id = tokens[1]
                log(f"[SYNC] Subscribed Token IDs: UP: ...{up_id[-8:]} | DOWN: ...{down_id[-8:]}")
                
                # Fetch initial REST order book snapshot
                r_up = requests.get(f"https://clob.polymarket.com/book?token_id={up_id}", headers=headers, timeout=3).json()
                r_dn = requests.get(f"https://clob.polymarket.com/book?token_id={down_id}", headers=headers, timeout=3).json()
                
                with ws_lock:
                    order_books[up_id] = {"asks": {float(x["price"]): float(x["size"]) for x in r_up.get("asks", [])}, "bids": {float(x["price"]): float(x["size"]) for x in r_up.get("bids", [])}}
                    order_books[down_id] = {"asks": {float(x["price"]): float(x["size"]) for x in r_dn.get("asks", [])}, "bids": {float(x["price"]): float(x["size"]) for x in r_dn.get("bids", [])}}
                    
                log("[SYNC] Initial REST order book snapshots loaded.")
        except Exception as e:
            log(f"[SYNC ERROR] {e}")
            
    time.sleep(1)
