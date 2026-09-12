import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

slug = "btc-updown-5m-1787958000"
r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
mkt = r[0]["markets"][0]
clob_ids = json.loads(mkt.get("clobTokenIds"))
up_tid = clob_ids[0]
down_tid = clob_ids[1]

print("Testing asset_id query for UP token:", up_tid)
p = requests.get(f"https://data-api.polymarket.com/trades?asset_id={up_tid}&limit=100").json()
print("Trade count for UP token:", len(p))
if p:
    print(f"Sample trade: Side={p[0].get('side')} Size={p[0].get('size')} Price={p[0].get('price')} Time={p[0].get('timestamp')}")
    for t in p[:5]:
        print(f"  • {t.get('side')} {t.get('size')} sh @ ${t.get('price')} (ts: {t.get('timestamp')})")

print("\nTesting asset_id query for DOWN token:", down_tid)
p_d = requests.get(f"https://data-api.polymarket.com/trades?asset_id={down_tid}&limit=100").json()
print("Trade count for DOWN token:", len(p_d))
if p_d:
    for t in p_d[:5]:
        print(f"  • {t.get('side')} {t.get('size')} sh @ ${t.get('price')} (ts: {t.get('timestamp')})")
