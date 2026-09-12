#!/usr/bin/env python3
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
print(f"🎯 5-SHARE LIMIT ORDER SCALPER ($0.98 Capital)")
print(f"   Wallet / Funder: {POLYMARKET_ADDRESS}")
print("="*90)

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
    except Exception as e:
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

def test_limit_order():
    now = time.time()
    mkt = get_market_tokens(now)
    if not mkt:
        print("No market found.")
        return

    # Find a cheap token priced <= $0.19 so 5.0 shares <= $0.98
    for side, tid in [("UP", mkt["up_id"]), ("DOWN", mkt["down_id"])]:
        bid, ask = probe_orderbook(tid)
        print(f"Token {side}: Best Bid=${bid}, Best Ask=${ask}")
        
        # If price <= 0.19, 5 shares costs <= 0.95
        if ask is not None and ask <= 0.19:
            cost = round(5.0 * ask, 2)
            print(f"\n🚀 Attempting 5.0 share Limit Buy on {side} @ ${ask:.3f} (Total Cost: ${cost:.2f} <= $0.98)...")
            try:
                args = OrderArgs(price=ask, size=5.0, side="BUY", token_id=tid)
                res = client.create_and_post_order(args)
                print(f"✅ LIMIT ORDER ACCEPTED! Response: {res}")
                return
            except Exception as e:
                print(f"❌ Limit order error: {e}")

if __name__ == "__main__":
    test_limit_order()
