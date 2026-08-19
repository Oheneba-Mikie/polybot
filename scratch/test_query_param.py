import requests
import json
import time

slug = "btc-updown-5m-1787140800" # 12:00 UTC cycle
r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
cid = r[0]["markets"][0]["conditionId"]
print(f"Slug: {slug}, CID: {cid}")

# Test with market={cid}
r1 = requests.get(f"https://data-api.polymarket.com/trades?market={cid}&limit=10").json()
print(f"Trades with market={cid}: {len(r1)} items")
if r1:
    print(r1[0])

# Test with clob.polymarket.com/data/trades
r2 = requests.get(f"https://clob.polymarket.com/data/trades?market={cid}&limit=10").json()
print(f"Trades from CLOB: {r2}")
