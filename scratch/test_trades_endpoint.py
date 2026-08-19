import requests
import json
import time

now_ts = time.time()
w_start = int(now_ts // 300) * 300
slug = f"btc-updown-5m-{w_start}"

r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=10).json()
condition_id = r[0]["markets"][0]["conditionId"]
print(f"Condition ID: {condition_id}")

# Fetch trades via data-api
r_trades = requests.get(f"https://data-api.polymarket.com/trades?condition_id={condition_id}&limit=50", timeout=10).json()
print(f"Fetched {len(r_trades)} trades from data-api for current cycle:")
for tr in r_trades[:15]:
    outcome = tr.get("outcome")
    side = tr.get("side")
    price = tr.get("price")
    size = tr.get("size")
    ts = tr.get("timestamp")
    print(f"  [{ts}] Side: {side} {outcome} @ ${price} (Size: {size:.1f} shares)")
