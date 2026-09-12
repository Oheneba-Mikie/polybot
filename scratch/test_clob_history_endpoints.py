import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

slug = "btc-updown-5m-1787958000"
r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
mkt = r[0]["markets"][0]
clob_ids = json.loads(mkt.get("clobTokenIds"))
tid = clob_ids[1] # DOWN token
cid = mkt.get("conditionId")

print("Checking Gamma API Market Details:")
print("Volume:", mkt.get("volume"))
print("Volume 24hr:", mkt.get("volume24hr"))
print("Outcome Prices:", mkt.get("outcomePrices"))
print("Orders/Trades stats:", mkt.get("volumeNum"))

# Test CLOB API endpoints
endpoints = [
    f"https://clob.polymarket.com/trades?asset_id={tid}",
    f"https://clob.polymarket.com/trades?market={tid}",
    f"https://clob.polymarket.com/last-trade-price?token_id={tid}",
    f"https://clob.polymarket.com/prices-history?market={tid}&interval=1m",
    f"https://clob.polymarket.com/prices-history?token_id={tid}&interval=1m",
]

for ep in endpoints:
    try:
        res = requests.get(ep, timeout=3)
        print(f"\nEndpoint: {ep} -> Status: {res.status_code}")
        if res.status_code == 200:
            print("Response:", str(res.json())[:300])
    except Exception as e:
        print(f"Error {ep}: {e}")
