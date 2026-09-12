import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

slug = "btc-updown-5m-1787958000"
r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
mkt = r[0]["markets"][0]
cid = mkt.get("conditionId")
tid = json.loads(mkt.get("clobTokenIds"))[0]

print("Testing conditionId:", cid)

# 1. Test data-api with conditionId
p1 = requests.get(f"https://data-api.polymarket.com/trades?conditionId={cid}&limit=10").json()
print("1. data-api ?conditionId count:", len(p1))
if p1: print("   Title:", p1[0].get("title"))

# 2. Test clob.polymarket.com/trades-history
p2 = requests.get(f"https://clob.polymarket.com/trades-history?market={tid}").json()
print("2. clob /trades-history count:", len(p2.get("data", [])) if isinstance(p2, dict) else len(p2))

# 3. Test gamma market trades or activity
p3 = requests.get(f"https://data-api.polymarket.com/activity?market={cid}&limit=10").json()
print("3. data-api /activity ?market count:", len(p3))
if p3: print("   Activity sample:", p3[0].get("type"), p3[0].get("title"))
