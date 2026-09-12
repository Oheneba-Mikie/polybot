import os
import sys
import json
import time
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

POLYMARKET_ADDRESS         = os.getenv("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY         = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET      = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE  = os.getenv("POLYMARKET_API_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY     = os.getenv("POLYMARKET_PRIVATE_KEY", "")

from py_clob_client_v2 import ClobClient, ApiCreds, TradeParams

creds = ApiCreds(
    api_key=POLYMARKET_API_KEY,
    api_secret=POLYMARKET_API_SECRET,
    api_passphrase=POLYMARKET_API_PASSPHRASE
)
client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=POLYMARKET_PRIVATE_KEY,
    creds=creds,
    signature_type=3,
    funder=POLYMARKET_ADDRESS
)

# Test with recent 5m market token
slug = "btc-updown-5m-1787958000"
import requests
r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
mkt = r[0]["markets"][0]
clob_ids = json.loads(mkt.get("clobTokenIds"))
tid = clob_ids[1] # DOWN token

print(f"Querying authenticated CLOB trades for DOWN token: {tid}...")
try:
    trades = client.get_trades(TradeParams(market=tid))
    print(f"Authenticated Trades Count: {len(trades)}")
    if trades:
        print("Sample Trade:", trades[0])
        for t in trades[:10]:
            print(f"  • Price: {t.get('price')} | Size: {t.get('size')} | Side: {t.get('side')} | Match Time: {t.get('match_time') or t.get('timestamp')}")
except Exception as e:
    print("CLOB get_trades Error:", e)
