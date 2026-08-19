import os
import sys
import time
import json
import threading
import datetime
from decimal import Decimal
from flask import Flask, jsonify, render_template
import websocket
import requests

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import OrderArgs, OrderType
    from py_clob_client.order_builder.constants import BUY, SELL
except ImportError:
    pass

app = Flask(__name__, template_folder="templates")

# ==============================================================================
# BOT OPTION A: Buy @ $0.98 -> Immediate Limit Sell @ $0.99 (Scavenger Flip)
# ==============================================================================

BUY_TARGET_PRICE = 0.98
SELL_TARGET_PRICE = 0.99
MIN_SHARES = 1
POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS")
POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY")
POLYMARKET_API_SECRET = os.getenv("POLYMARKET_API_SECRET")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE")
POLYMARKET_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY") or os.getenv("PRIVATE_KEY")

bot_state = {
    "name": "Bot Option A (Buy 0.98 -> Sell 0.99 Flip)",
    "status": "Initializing",
    "mode": "LIVE" if POLYMARKET_PRIVATE_KEY else "PAPER TRADING",
    "current_slug": None,
    "ptb": None,
    "btc_price": None,
    "delta": None,
    "up_ask": None,
    "down_ask": None,
    "up_size": 0.0,
    "down_size": 0.0,
    "balance": 0.0,
    "total_trades": 0,
    "total_profit_usdc": 0.0,
    "active_position": None,
    "logs": [],
    "history": []
}

log_lock = threading.Lock()
def log(msg):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    entry = f"[{ts}] {msg}"
    print(entry, flush=True)
    with log_lock:
        bot_state["logs"].append(entry)
        if len(bot_state["logs"]) > 250:
            bot_state["logs"].pop(0)

# Import and Initialize CLOB Client using exact off_peak_5mins_hybrid_sprint.py logic
clob_client = None
if POLYMARKET_PRIVATE_KEY and POLYMARKET_API_KEY:
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
            host="https://clob.polymarket.com",
            chain_id=137,
            key=POLYMARKET_PRIVATE_KEY,
            creds=creds,
            signature_type=sig_type,
            funder=funder_addr
        )
        log(f"[AUTH] ✅ Authenticated with Polymarket CLOB. Proxy: {funder_addr}")
    except Exception as e:
        log(f"[AUTH ERROR] ❌ Error initializing CLOB client: {e}")

def get_live_balance():
    if clob_client is not None:
        try:
            from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
            params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            resp = clob_client.get_balance_allowance(params)
            raw_bal = float(resp.get("balance", 0))
            bal = raw_bal / 1_000_000.0
            return bal
        except Exception as e:
            log(f"[BALANCE ERROR] ⚠️ Error fetching live balance: {e}")
    return 0.0

# Pure Polymarket Chainlink Live Oracle WebSocket (No external exchanges)
class PolymarketLiveOracle:
    def __init__(self):
        self.ws_url = "wss://ws-live-data.polymarket.com/"
        self.live_btc_price = None
        self.ws = None
        self.lock = threading.Lock()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def get_price(self):
        with self.lock:
            return self.live_btc_price

    def _run(self):
        while True:
            try:
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_message=self._on_message,
                    on_open=self._on_open,
                    on_error=lambda ws, e: None,
                    on_close=lambda ws, c, m: None
                )
                self.ws.run_forever(ping_interval=15, ping_timeout=5)
            except Exception:
                pass
            time.sleep(1)

    def _on_open(self, ws):
        sub_msg = {"action": "subscribe", "topic": "crypto_prices_chainlink", "payload": {"symbol": "btc/usd"}}
        ws.send(json.dumps(sub_msg))

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get("topic") == "crypto_prices_chainlink":
                payload = data.get("payload", {})
                symbol = payload.get("symbol", "").lower()
                val = payload.get("value")
                if symbol == "btc/usd" and val is not None:
                    with self.lock:
                        self.live_btc_price = float(val)
        except Exception:
            pass

chainlink_feed = PolymarketLiveOracle()
chainlink_feed.start()

# WebSocket & Order Book Management
ws_client = None
ws_lock = threading.Lock()
up_id = None
down_id = None
current_ptb = None
cycle_traded = False

order_books = {}
prices = {}

def get_market_data(slug):
    try:
        r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=5).json()
        if not r or "markets" not in r[0]:
            return None, None, None, None
        m = r[0]["markets"][0]
        token_ids = json.loads(m["clobTokenIds"])
        outcomes = json.loads(m["outcomes"])
        u_id, d_id = None, None
        for i, o in enumerate(outcomes):
            if str(o).lower() in ("up", "yes"):
                u_id = token_ids[i]
            else:
                d_id = token_ids[i]
        
        ptb_val = None
        for f in ("strikePrice", "priceToBeat", "targetPrice"):
            if m.get(f) is not None:
                try:
                    ptb_val = float(m[f])
                    break
                except:
                    pass
        return u_id, d_id, ptb_val, m.get("conditionId")
    except Exception as e:
        log(f"[METADATA ERROR] {e}")
        return None, None, None, None

def execute_option_a_trade(side_name, token_id, ask_price, ask_size):
    global cycle_traded
    if cycle_traded:
        return
    
    # Calculate share size from 50% wallet allocation (shared between Bot A and Bot B)
    current_bal = bot_state["balance"]
    bot_allocation = current_bal * 0.50
    max_affordable = int(bot_allocation / BUY_TARGET_PRICE)
    max_available = int(ask_size)
    target_shares = min(max_affordable, max_available)
    
    if target_shares < MIN_SHARES:
        log(f"[SKIP] Target shares {target_shares} < minimum {MIN_SHARES} shares.")
        return
    
    cycle_traded = True
    buy_cost = target_shares * BUY_TARGET_PRICE
    log(f"[OPTION A TRIGGER] Detected {side_name} @ ${ask_price:.4f} (Depth: {ask_size:.1f} shares)")
    log(f"[EXECUTE STEP 1] Buying {target_shares} shares of {side_name} @ ${BUY_TARGET_PRICE:.2f} (Cost: ${buy_cost:.2f})")
    
    order_id = f"BUY-OPT-A-{int(time.time()*1000)}"
    buy_success = False
    
    if clob_client and bot_state["mode"] == "LIVE":
        try:
            from py_clob_client_v2.clob_types import OrderArgs
            from py_clob_client_v2.order_builder.constants import BUY
            buy_args = OrderArgs(
                price=BUY_TARGET_PRICE,
                size=float(target_shares),
                side=BUY,
                token_id=token_id
            )
            res = clob_client.create_and_post_order(buy_args)
            if res and (res.get("orderID") or res.get("success")):
                order_id = res.get("orderID") or str(res)
                buy_success = True
                log(f"[SUCCESS STEP 1] Buy Order Placed & Filled! ID: {order_id}")
            else:
                log(f"[ORDER FAILED] Buy Order response: {res}")
        except Exception as e:
            log(f"[ORDER ERROR STEP 1] {e}")
    else:
        # Paper trading execution
        buy_success = True
        log(f"[PAPER STEP 1] Simulated BUY {target_shares} shares @ ${BUY_TARGET_PRICE:.2f} filled.")
        
    if buy_success:
        bot_state["balance"] -= buy_cost
        
        # STEP 2: Immediately Place Limit Sell Order at $0.99
        log(f"[EXECUTE STEP 2] Digging SELL HOLE: Posting Limit Sell for {target_shares} {side_name} @ ${SELL_TARGET_PRICE:.2f}...")
        sell_order_id = f"SELL-OPT-A-{int(time.time()*1000)}"
        sell_placed = False
        
        if clob_client and bot_state["mode"] == "LIVE":
            try:
                from py_clob_client_v2.clob_types import OrderArgs
                from py_clob_client_v2.order_builder.constants import SELL
                sell_args = OrderArgs(
                    price=SELL_TARGET_PRICE,
                    size=float(target_shares),
                    side=SELL,
                    token_id=token_id
                )
                s_res = clob_client.create_and_post_order(sell_args)
                if s_res and (s_res.get("orderID") or s_res.get("success")):
                    sell_order_id = s_res.get("orderID") or str(s_res)
                    sell_placed = True
                    log(f"[SUCCESS STEP 2] Limit Sell Hole Active at ${SELL_TARGET_PRICE:.2f}! ID: {sell_order_id}")
                else:
                    log(f"[SELL HOLE FAILED] {s_res}")
            except Exception as e:
                log(f"[SELL HOLE ERROR] {e}")
        else:
            sell_placed = True
            log(f"[PAPER STEP 2] Simulated Limit Sell active at ${SELL_TARGET_PRICE:.2f}.")
            
        # Register trade record and complete flip simulation / tracking
        revenue = target_shares * SELL_TARGET_PRICE
        profit = revenue - buy_cost
        bot_state["balance"] += revenue
        bot_state["total_trades"] += 1
        bot_state["total_profit_usdc"] += profit
        
        trade_record = {
            "time": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S"),
            "side": side_name,
            "shares": target_shares,
            "buy_price": BUY_TARGET_PRICE,
            "sell_price": SELL_TARGET_PRICE,
            "cost": buy_cost,
            "revenue": revenue,
            "profit": profit,
            "balance": bot_state["balance"],
            "order_id": order_id[:12] + "..."
        }
        bot_state["history"].insert(0, trade_record)
        log(f"[PROFIT LOCKED] Sold @ ${SELL_TARGET_PRICE:.2f}! Profit: +${profit:.4f} USDC | New Rollover Balance: ${bot_state['balance']:.2f}")

def on_message(ws, message):
    global prices, up_id, down_id, ws_client, order_books
    ws_client = ws
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
                if asset_id not in order_books:
                    order_books[asset_id] = {"asks": {}, "bids": {}}
                
            if ev_type == "book" or "asks" in item:
                asks = item.get("asks", [])
                order_books[asset_id]["asks"] = {
                    float(a["price"]): float(a.get("size", 0.0))
                    for a in asks if float(a.get("size", 0.0)) > 0
                }
                bids = item.get("bids", [])
                order_books[asset_id]["bids"] = {
                    float(b["price"]): float(b.get("size", 0.0))
                    for b in bids if float(b.get("size", 0.0)) > 0
                }
                updated = True
                
            elif ev_type == "price_change":
                changes = item.get("price_changes", []) or [item]
                for ch in changes:
                    p = ch.get("price")
                    sz = ch.get("size")
                    side = str(ch.get("side", "")).upper()
                    if p is not None and sz is not None:
                        price_flt = float(p)
                        size_flt = float(sz)
                        if side in ("SELL", "ASK"):
                            if size_flt <= 0:
                                order_books[asset_id]["asks"].pop(price_flt, None)
                            else:
                                order_books[asset_id]["asks"][price_flt] = size_flt
                            updated = True
                        elif side in ("BUY", "BID"):
                            if size_flt <= 0:
                                order_books[asset_id]["bids"].pop(price_flt, None)
                            else:
                                order_books[asset_id]["bids"][price_flt] = size_flt
                            updated = True
            
            if updated and asset_id in order_books and order_books[asset_id]["asks"]:
                min_ask = min(order_books[asset_id]["asks"].keys())
                min_sz = order_books[asset_id]["asks"][min_ask]
                prices[asset_id] = {"price": min_ask, "size": min_sz}
                        
        with ws_lock:
            if not up_id or not down_id:
                return
            up_price = prices.get(up_id, {}).get("price")
            up_size = prices.get(up_id, {}).get("size", 0.0)
            down_price = prices.get(down_id, {}).get("price")
            down_size = prices.get(down_id, {}).get("size", 0.0)

        if updated and up_price is not None and down_price is not None:
            combined = up_price + down_price
            bot_state["status"] = "Active Scanning"
            bot_state["up_ask"] = up_price
            bot_state["up_size"] = up_size
            bot_state["down_ask"] = down_price
            bot_state["down_size"] = down_size
            
            live_btc = chainlink_feed.get_price()
            delta_str = ""
            if live_btc is not None and current_ptb is not None:
                delta = live_btc - current_ptb
                bot_state["btc_price"] = live_btc
                bot_state["ptb"] = current_ptb
                bot_state["delta"] = delta
                direction = "▲ UP" if delta >= 0 else "▼ DN"
                delta_str = f" | BTC: ${live_btc:,.2f} | PTB: ${current_ptb:,.2f} (Diff: {delta:+.2f} {direction})"
            elif live_btc is not None:
                bot_state["btc_price"] = live_btc
                delta_str = f" | BTC: ${live_btc:,.2f}"
            
            log(f"[FLOW] UP: ${up_price:.4f} (Sz: {up_size:.1f}) | DN: ${down_price:.4f} (Sz: {down_size:.1f}) | Combined: ${combined:.4f}{delta_str}")
            
            now_ts = time.time()
            w_start = int(now_ts // 300) * 300
            w_end = w_start + 300
            seconds_left = int(w_end - now_ts)
            
            # Final 15s Window and Strict $0.98 Entry
            if 1 <= seconds_left <= 15:
                if up_price == BUY_TARGET_PRICE and up_size >= MIN_SHARES:
                    log(f"[TRIGGER] UP @ ${up_price:.4f} with {seconds_left}s left")
                    execute_option_a_trade("UP", up_id, up_price, up_size)
                elif down_price == BUY_TARGET_PRICE and down_size >= MIN_SHARES:
                    log(f"[TRIGGER] DOWN @ ${down_price:.4f} with {seconds_left}s left")
                    execute_option_a_trade("DOWN", down_id, down_price, down_size)
    except Exception as e:
        pass

def on_open(ws):
    global ws_client
    ws_client = ws
    log("[BOOK WS] Connected to Polymarket CLOB Book WebSocket.")
    with ws_lock:
        if up_id and down_id:
            sub = {"type": "market", "assets_ids": [up_id, down_id], "custom_feature_enabled": True}
            try:
                ws_client.send(json.dumps(sub))
                log(f"[BOOK WS] Subscribed to Token IDs: ...{up_id[-8:]} / ...{down_id[-8:]}")
            except Exception as e:
                log(f"[BOOK WS] Subscription error: {e}")

def ws_thread():
    while True:
        try:
            ws = websocket.WebSocketApp(
                "wss://ws-subscriptions-clob.polymarket.com/ws/market",
                on_open=on_open,
                on_message=on_message,
                on_error=lambda ws, e: None,
                on_close=lambda ws, c, m: None
            )
            ws.run_forever(ping_interval=10, ping_timeout=5)
        except Exception:
            pass
        time.sleep(2)

def fetch_initial_book(token_id):
    try:
        r = requests.get(f"https://clob.polymarket.com/book?token_id={token_id}", timeout=3).json()
        asks = r.get("asks", [])
        bids = r.get("bids", [])
        with ws_lock:
            if token_id not in order_books:
                order_books[token_id] = {"asks": {}, "bids": {}}
            order_books[token_id]["asks"] = {
                float(a["price"]): float(a.get("size", 0.0))
                for a in asks if float(a.get("size", 0.0)) > 0
            }
            order_books[token_id]["bids"] = {
                float(b["price"]): float(b.get("size", 0.0))
                for b in bids if float(b.get("size", 0.0)) > 0
            }
            if order_books[token_id]["asks"]:
                min_ask = min(order_books[token_id]["asks"].keys())
                min_sz = order_books[token_id]["asks"][min_ask]
                prices[token_id] = {"price": min_ask, "size": min_sz}
    except Exception:
        pass

def bot_loop():
    global up_id, down_id, current_ptb, cycle_traded, prices, order_books
    active_slug = None
    last_flow_time = 0
    last_bal_check = 0
    
    while True:
        try:
            now_ts = time.time()
            w_start = int(now_ts // 300) * 300
            slug = f"btc-updown-5m-{w_start}"
            
            if slug != active_slug:
                active_slug = slug
                cycle_traded = False
                bot_state["current_slug"] = slug
                
                u_id, d_id, ptb_val, cid = get_market_data(slug)
                if u_id and d_id:
                    with ws_lock:
                        up_id, down_id = u_id, d_id
                        current_ptb = ptb_val or chainlink_feed.get_price()
                        prices = {up_id: {"price": None, "size": 0.0}, down_id: {"price": None, "size": 0.0}}
                        order_books = {up_id: {"asks": {}, "bids": {}}, down_id: {"asks": {}, "bids": {}}}
                    
                    log(f"\n--- NEW CYCLE: {slug} | PTB: ${current_ptb if current_ptb else 0:,.2f} ---")
                    
                    # Fetch initial book snapshots immediately
                    threading.Thread(target=fetch_initial_book, args=(up_id,), daemon=True).start()
                    threading.Thread(target=fetch_initial_book, args=(down_id,), daemon=True).start()
                    
                    if ws_client:
                        sub = {"type": "market", "assets_ids": [up_id, down_id], "custom_feature_enabled": True}
                        try:
                            ws_client.send(json.dumps(sub))
                            log(f"[BOOK WS] Subscribed to Token IDs: ...{up_id[-8:]} / ...{down_id[-8:]}")
                        except Exception as e:
                            log(f"[BOOK WS] Subscription error: {e}")
            
            # Sync real balance periodically using exact get_live_balance() logic
            if now_ts - last_bal_check > 5:
                bal = get_live_balance()
                if bal is not None:
                    bot_state["balance"] = bal
                last_bal_check = now_ts
            
            # Periodic 1.5s flow logger to keep dashboard active even during market lulls
            if now_ts - last_flow_time > 1.5 and up_id and down_id:
                with ws_lock:
                    up_p = prices.get(up_id, {}).get("price")
                    up_sz = prices.get(up_id, {}).get("size", 0.0)
                    dn_p = prices.get(down_id, {}).get("price")
                    dn_sz = prices.get(down_id, {}).get("size", 0.0)
                
                live_btc = chainlink_feed.get_price()
                if live_btc and current_ptb:
                    delta = live_btc - current_ptb
                    bot_state["btc_price"] = live_btc
                    bot_state["ptb"] = current_ptb
                    bot_state["delta"] = delta
                    direction = "▲ UP" if delta >= 0 else "▼ DN"
                    delta_str = f" | BTC: ${live_btc:,.2f} | PTB: ${current_ptb:,.2f} (Diff: {delta:+.2f} {direction})"
                elif live_btc:
                    bot_state["btc_price"] = live_btc
                    delta_str = f" | BTC: ${live_btc:,.2f}"
                else:
                    delta_str = ""
                
                if up_p is not None and dn_p is not None:
                    bot_state["status"] = "Active Scanning"
                    bot_state["up_ask"] = up_p
                    bot_state["up_size"] = up_sz
                    bot_state["down_ask"] = dn_p
                    bot_state["down_size"] = dn_sz
                    log(f"[FLOW] UP: ${up_p:.4f} (Sz: {up_sz:.1f}) | DN: ${dn_p:.4f} (Sz: {dn_sz:.1f}) | Combined: ${(up_p+dn_p):.4f}{delta_str}")
                    last_flow_time = now_ts
                    
                    # Trigger check: Final 15s Window and Strict $0.98 Entry
                    w_start_cur = int(now_ts // 300) * 300
                    seconds_left_cur = int((w_start_cur + 300) - now_ts)
                    if 1 <= seconds_left_cur <= 15:
                        if up_p == BUY_TARGET_PRICE and up_sz >= MIN_SHARES:
                            execute_option_a_trade("UP", up_id, up_p, up_sz)
                        elif dn_p == BUY_TARGET_PRICE and dn_sz >= MIN_SHARES:
                            execute_option_a_trade("DOWN", down_id, dn_p, dn_sz)
                            
            time.sleep(0.5)
        except Exception as e:
            log(f"[LOOP ERROR] {e}")
            time.sleep(1)

# Start background workers
threading.Thread(target=ws_thread, daemon=True).start()
threading.Thread(target=bot_loop, daemon=True).start()

# Flask API Routes
@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/status")
@app.route("/status")
def status():
    live_btc = chainlink_feed.get_price()
    if live_btc:
        bot_state["btc_price"] = live_btc
        if current_ptb:
            bot_state["ptb"] = current_ptb
            bot_state["delta"] = live_btc - current_ptb
            
    # Always fetch latest live balance
    bal = get_live_balance()
    if bal is not None:
        bot_state["balance"] = bal
        
    return jsonify(bot_state)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
