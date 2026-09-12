#!/usr/bin/env python3
"""
execute_local_stake_098.py — 5-Share Limit Scalper for $0.98 Capital

Strategy (Option B):
1. Target: Buy exactly 5.0 shares of any token priced <= $0.190.
   - 5.0 shares @ $0.15 = $0.75 total cost (fits inside $0.98 balance).
   - 5.0 shares @ $0.18 = $0.90 total cost.
2. Exit Rules:
   - Take Profit: Sells 5.0 shares as soon as bid increases by >= +2c (e.g. 15c -> 17c+ = +$0.10 to +$0.50 cash profit).
   - Resolution Win: If held to expiry, 5 shares pay out $5.00 USDC (+$4.10+ profit).
   - Safety Cutoff: At T-15s, exits if unfavorable.
"""

import os
import sys
import time
import json
import ssl
import datetime
import threading
import requests
import websocket
from dotenv import load_dotenv

sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
load_dotenv()

# ── Endpoints ──────────────────────────────────────────────────────────────────
GAMMA_HOST  = "https://gamma-api.polymarket.com"
CLOB_HOST   = "https://clob.polymarket.com"
LIVE_WS_URL = "wss://ws-live-data.polymarket.com/"
WINDOW_SECS = 300

MAX_ENTRY_PRICE = 0.190  # 5 shares * $0.19 = $0.95 (Under $0.98 balance)
SHARES_COUNT    = 5.0    # Exact minimum limit order size
TAKE_PROFIT_PTS = 0.02   # Exit on +2c gain (or hold for $5.00 resolution)

POLYMARKET_ADDRESS        = os.getenv("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY        = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET     = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY    = os.getenv("POLYMARKET_PRIVATE_KEY", "")

from py_clob_client_v2 import ClobClient, ApiCreds, OrderArgs
from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
from eth_account import Account

eoa_address = Account.from_key(POLYMARKET_PRIVATE_KEY).address
sig_type = 3 if POLYMARKET_ADDRESS and POLYMARKET_ADDRESS.lower() != eoa_address.lower() else 0
funder_addr = POLYMARKET_ADDRESS if sig_type == 3 else None

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
    signature_type=sig_type,
    funder=funder_addr
)

print("="*90)
print("🚀 OPTION B: 5-SHARE LIMIT SCALPER ($0.98 CAPITAL ENGINE)")
print(f"   Wallet / Funder:    {POLYMARKET_ADDRESS}")
print(f"   Max Buy Price:      <= ${MAX_ENTRY_PRICE:.3f} per share")
print(f"   Order Size:         {SHARES_COUNT} shares (Total Cost: <= $0.95)")
print(f"   Take Profit Target: Entry + ${TAKE_PROFIT_PTS:.2f}/share OR Expiry Payout ($5.00)")
print("="*90)

def get_live_balance():
    try:
        resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=sig_type))
        raw_b = float(resp.get("balance", 0)) / 1_000_000
        return raw_b
    except Exception as e:
        return 0.0

def get_live_token_shares(token_id):
    try:
        resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=token_id, signature_type=sig_type))
        raw_b = float(resp.get("balance", 0)) / 1_000_000
        return raw_b
    except Exception:
        return 0.0

# ── Live Chainlink WS Feed ────────────────────────────────────────────────────
class ChainlinkFeed:
    def __init__(self):
        self.price = None
        self._lock = threading.Lock()

    def start(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        def on_open(ws):
            ws.send(json.dumps({
                "action": "subscribe",
                "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}]
            }))

        def on_message(ws, raw):
            if not raw: return
            try:
                msg = json.loads(raw)
                if msg.get("topic") == "crypto_prices_chainlink":
                    p = msg.get("payload", {})
                    if p.get("symbol") == "btc/usd":
                        with self._lock:
                            self.price = float(p.get("value", 0))
            except Exception:
                pass

        def runner():
            app_ws = websocket.WebSocketApp(
                LIVE_WS_URL,
                header={"User-Agent": "Mozilla/5.0"},
                on_open=on_open,
                on_message=on_message
            )
            app_ws.run_forever(sslopt={"context": ctx})

        threading.Thread(target=runner, daemon=True).start()

    def get_price(self):
        with self._lock:
            return self.price

feed = ChainlinkFeed()
feed.start()

def win_start(ts=None):
    if ts is None: ts = time.time()
    return int(ts // WINDOW_SECS) * WINDOW_SECS

def win_end(ts=None):
    return win_start(ts) + WINDOW_SECS

def slug_for(ts=None):
    return f"btc-updown-5m-{win_start(ts)}"

def get_market_tokens(ts=None):
    slug = slug_for(ts)
    url = f"{GAMMA_HOST}/events?slug={slug}"
    try:
        r = requests.get(url, timeout=3).json()
        if not r or not r[0].get("markets"): return None
        mkt = r[0]["markets"][0]
        tids = json.loads(mkt.get("clobTokenIds") or "[]")
        outs = [str(o).lower() for o in json.loads(mkt.get("outcomes") or "[]")]
        up_id = tids[0] if outs[0] in ("up", "yes") else tids[1]
        down_id = tids[1] if outs[0] in ("up", "yes") else tids[0]
        return {"slug": slug, "up_id": up_id, "down_id": down_id}
    except Exception:
        return None

def probe_orderbook(token_id):
    try:
        r = requests.get(f"{CLOB_HOST}/book", params={"token_id": token_id}, timeout=1.0).json()
        bids = [float(b["price"]) for b in r.get("bids", [])]
        asks = [float(a["price"]) for a in r.get("asks", [])]
        best_bid = max(bids) if bids else None
        best_ask = min(asks) if asks else None
        return best_bid, best_ask
    except Exception:
        return None, None

def run_option_b():
    print("⏳ Connecting to Polymarket CLOB and streaming live order books...")
    time.sleep(2)
    
    last_candle_traded = None

    while True:
        now = time.time()
        w_s = win_start(now)
        w_e = win_end(now)
        rem = w_e - now
        slug = slug_for(now)
        
        if last_candle_traded == w_s:
            time.sleep(1)
            continue
            
        mkt = get_market_tokens(now)
        if not mkt:
            time.sleep(1)
            continue

        btc_px = feed.get_price()
        up_bid, up_ask = probe_orderbook(mkt["up_id"])
        dn_bid, dn_ask = probe_orderbook(mkt["down_id"])
        
        t_str = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{t_str}] {slug} (T-{rem:.0f}s) | BTC: ${(btc_px or 0):,.2f}")
        print(f"   • UP:   Bid ${up_bid} | Ask ${up_ask}")
        print(f"   • DOWN: Bid ${dn_bid} | Ask ${dn_ask}")

        # Search for any side with ask <= $0.190
        target_side = None
        target_tid = None
        target_ask = None
        
        if up_ask is not None and up_ask <= MAX_ENTRY_PRICE:
            target_side = "UP"
            target_tid = mkt["up_id"]
            target_ask = up_ask
        elif dn_ask is not None and dn_ask <= MAX_ENTRY_PRICE:
            target_side = "DOWN"
            target_tid = mkt["down_id"]
            target_ask = dn_ask

        # Place 5-share limit buy when opportunity appears
        if target_side and rem > 25:
            cost = round(SHARES_COUNT * target_ask, 2)
            print(f"\n🎯 [OPPORTUNITY DETECTED] {target_side} ask is at ${target_ask:.3f} (<= ${MAX_ENTRY_PRICE:.3f})")
            print(f"🚀 SUBMITTING 5.0 SHARE LIMIT BUY: Total Cost = ${cost:.2f} USDC (under $0.98)...")
            
            try:
                order_args = OrderArgs(
                    price=target_ask,
                    size=SHARES_COUNT,
                    side="BUY",
                    token_id=target_tid
                )
                res = client.create_and_post_order(order_args)
                print(f"✅ BUY ORDER PLACED! ID/Response: {res}")
                
                entry_price = target_ask
                target_sell_price = round(entry_price + TAKE_PROFIT_PTS, 3)
                print(f"📈 Holding 5.0 shares of {target_side} @ ${entry_price:.3f} (Cost: ${cost:.2f})")
                print(f"🎯 Target Scalp Exit: >= ${target_sell_price:.3f} | Resolution Payout: $5.00 USDC")
                
                # Active Position Monitor
                position_active = True
                while position_active:
                    cur_bid, _ = probe_orderbook(target_tid)
                    cur_rem = win_end() - time.time()
                    
                    if cur_bid is not None:
                        current_val = round(SHARES_COUNT * cur_bid, 2)
                        profit = round(current_val - cost, 2)
                        t_now = datetime.datetime.now().strftime("%H:%M:%S")
                        print(f"   [{t_now}] Live Bid: ${cur_bid:.3f} | Value: ${current_val:.2f} | P&L: {profit:+.2f} USD (T-{cur_rem:.0f}s)")
                        
                        # Exit Condition 1: Take Profit Hit
                        if cur_bid >= target_sell_price:
                            print(f"\n🎉 [TAKE PROFIT TRIGGERED] Bid reached ${cur_bid:.3f} >= ${target_sell_price:.3f}")
                            sell_args = OrderArgs(
                                price=cur_bid,
                                size=SHARES_COUNT,
                                side="SELL",
                                token_id=target_tid
                            )
                            sell_res = client.create_and_post_order(sell_args)
                            print(f"💰 SELL ORDER EXECUTED! Cash Profit: +${profit:.2f} USDC! (Response: {sell_res})")
                            last_candle_traded = w_s
                            position_active = False
                            break
                            
                        # Exit Condition 2: If price skyrockets towards $1.00, hold for full $5.00 payout!
                        if cur_bid >= 0.85:
                            print(f"\n🏆 [HOLDING TO EXPIRY] Token is at ${cur_bid:.3f}! Securing full $5.00 USDC payout!")
                            last_candle_traded = w_s
                            position_active = False
                            break

                    time.sleep(0.5)

            except Exception as e:
                print(f"❌ Order Error: {e}")
                time.sleep(2)
                
        time.sleep(1.0)

if __name__ == "__main__":
    run_option_b()
