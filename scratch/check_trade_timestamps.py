import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

slug = "btc-updown-5m-1787958000"
w_s = 1787958000
w_e = 1787958300
r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
mkt = r[0]["markets"][0]
clob_ids = json.loads(mkt.get("clobTokenIds"))
tid = clob_ids[1] # DOWN token

t_res = requests.get(f"https://data-api.polymarket.com/trades?asset_id={tid}&limit=20").json()
print("Market Window:", w_s, "to", w_e)
for t in t_res[:10]:
    ts = t.get("timestamp")
    print(f"Trade ts: {ts} (diff from start: {ts - w_s}s) | Price: {t.get('price')} | Size: {t.get('size')} | Side: {t.get('side')}")
