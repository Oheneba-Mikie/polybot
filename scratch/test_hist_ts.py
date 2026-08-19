import requests
import json
import time

slug = "btc-updown-5m-1787140800" # 12:00 UTC cycle
r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
cid = r[0]["markets"][0]["conditionId"]
print(f"Condition ID for 12:00 UTC: {cid}")

r_tr = requests.get(f"https://data-api.polymarket.com/trades?condition_id={cid}&limit=20").json()
for tr in r_tr[:10]:
    ts = tr.get("timestamp")
    t_dt = time.strftime("%H:%M:%S", time.gmtime(ts))
    print(f"[{t_dt} UTC] Side: {tr.get('side')} {tr.get('outcome')} @ ${tr.get('price')} (Sz: {tr.get('size')}) | Raw TS: {ts}")
