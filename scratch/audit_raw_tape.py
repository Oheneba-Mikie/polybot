import os
import sys
import json
import time
import datetime
import requests

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST = "https://data-api.polymarket.com"

# Let's inspect the exact trade tape for the 17:25 UTC candle (btc-updown-5m-1787419500)
# and 17:30 UTC candle
now = time.time()
current_w_s = int(now // 300) * 300
ts_1725 = 1787419500 # or recent timestamp

print("="*100)
print("🔍 AUDITING RAW TRADE-BY-TRADE TAPE TO SEE EXACTLY HOW 0.97 AND 0.98 OCCUR OVER TIME")
print("="*100)

# Fetch recent 5m market
r = requests.get(f"{GAMMA_HOST}/events?limit=10&closed=true").json()
target_event = None
for ev in r:
    if "btc-updown-5m" in ev.get("slug", ""):
        target_event = ev
        break

if not target_event:
    # Try with slug format
    slug = f"btc-updown-5m-{current_w_s - 600}"
    r = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
    if r: target_event = r[0]

if not target_event:
    print("Could not find recent closed market.")
    sys.exit(0)

mkt = target_event["markets"][0]
cid = mkt["conditionId"]
slug = target_event["slug"]
print(f"Auditing Market: {slug} ({mkt.get('question')})\n")

r_trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=200").json()
if not r_trades:
    print("No trades found.")
    sys.exit(0)

# Sort strictly by timestamp ascending
trades = sorted(r_trades, key=lambda x: (x.get("timestamp", 0), float(x.get("price", 0))))

print(f"{'#':<4} | {'TIMESTAMP (UTC)':<19} | {'OUTCOME':<6} | {'SIDE':<5} | {'PRICE':<7} | {'SHARES':<10} | {'USDC VALUE'}")
print("="*85)

for i, t in enumerate(trades[:60]):
    ts = t.get("timestamp", 0)
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M:%S")
    outcome = str(t.get("outcome", "")).upper()
    side = str(t.get("side", "")).upper()
    px = float(t.get("price", 0))
    sz = float(t.get("size", 0))
    usd = px * sz
    print(f"{i+1:<4} | {dt_str:<19} | {outcome:<6} | {side:<5} | ${px:<6.2f} | {sz:<10.2f} | ${usd:.2f}")

# Look at 0.97 and 0.98 sequences specifically
print("\n" + "="*85)
print("FILTERING SPECIFICALLY FOR TRADES AT $0.96, $0.97, $0.98, $0.99:")
print("="*85)

high_trades = [t for t in trades if float(t.get("price", 0)) >= 0.95]
print(f"{'#':<4} | {'TIME (UTC)':<12} | {'OUTCOME':<6} | {'PRICE':<6} | {'SHARES':<10} | {'TIME GAP SINCE LAST HIGH TRADE'}")
print("-"*85)

last_ts = None
for i, t in enumerate(high_trades[:40]):
    ts = t.get("timestamp", 0)
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M:%S")
    outcome = str(t.get("outcome", "")).upper()
    px = float(t.get("price", 0))
    sz = float(t.get("size", 0))
    gap_str = f"+{ts - last_ts}s" if last_ts is not None else "Start"
    last_ts = ts
    print(f"{i+1:<4} | {dt_str:<12} | {outcome:<6} | ${px:<5.2f} | {sz:<10.2f} | {gap_str}")

with open("scratch/raw_tape_audit.json", "w") as fp:
    json.dump(trades, fp, indent=2)
