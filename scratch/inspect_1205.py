import requests
import json
import datetime
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

slug = "btc-updown-5m-1789646700"
r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
cid = r[0]["markets"][0]["conditionId"]
outcomes = json.loads(r[0]["markets"][0]["outcomes"])
out_prices = json.loads(r[0]["markets"][0]["outcomePrices"])
print(f"Market: {slug} (12:05 UTC)")
print(f"Outcomes: {outcomes} | Prices: {out_prices}")

trades = requests.get(f"https://data-api.polymarket.com/trades?market={cid}&limit=1000").json()
w_s = 1789646700
print(f"Total trades: {len(trades)}")

# Sort by timestamp
parsed = []
for t in trades:
    tr_ts = float(t.get("timestamp") or 0)
    if tr_ts > 1e11:
        tr_ts /= 1000.0
    sec = int(tr_ts - w_s)
    parsed.append((sec, t.get("side"), float(t.get("size", 0)), t.get("outcome"), float(t.get("price", 0))))

parsed.sort(key=lambda x: x[0])
for sec, side, sz, oc, px in parsed:
    if px >= 0.80 or px <= 0.20:
        print(f"  T+{sec:03d}s: {side} {sz:.1f}sh {oc} @ ${px:.3f}")
