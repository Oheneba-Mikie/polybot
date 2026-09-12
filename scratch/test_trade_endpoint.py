import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Test querying a known recent closed market e.g. btc-updown-5m-1787958000
slug = "btc-updown-5m-1787958000"
r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
if r:
    mkt = r[0]["markets"][0]
    print("Market title:", mkt.get("question"))
    print("Condition ID:", mkt.get("conditionId"))
    print("CLOB Token IDs:", mkt.get("clobTokenIds"))
    
    cid = mkt.get("conditionId")
    tid = json.loads(mkt.get("clobTokenIds"))[0]
    
    # Try Data API
    r_trades = requests.get(f"https://data-api.polymarket.com/trades?condition_id={cid}&limit=20").json()
    print("Trades from Data API (condition_id):", len(r_trades))
    if r_trades:
        print("Sample Trade:", json.dumps(r_trades[0], indent=2))
        
    r_trades_m = requests.get(f"https://data-api.polymarket.com/trades?market={tid}&limit=20").json()
    print("Trades from Data API (market/asset_id):", len(r_trades_m))
