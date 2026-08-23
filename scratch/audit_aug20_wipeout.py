import sys
import json
import datetime
import requests

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
POLYMARKET_ADDRESS = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"

print("="*90)
print("🔍 AUDITING AUGUST 20 LOSS ($35.32 WIPE-OUT) - WHY DID IT HAPPEN?")
print("="*90)

r_act = requests.get(f"{DATA_HOST}/activity?user={POLYMARKET_ADDRESS}&limit=100").json()

aug20_acts = []
for a in r_act:
    ts = a.get("timestamp", 0)
    dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
    if dt.day == 20 and dt.month == 8 and dt.year == 2026:
        aug20_acts.append(a)

aug20_acts = sorted(aug20_acts, key=lambda x: x.get("timestamp", 0))

print(f"Fetched {len(aug20_acts)} activity records from August 20.\n")
print(f"{'TIMESTAMP (UTC)':<19} | {'ACTION':<6} | {'PRICE':<6} | {'SHARES':<7} | {'USDC AMOUNT':<12} | {'TITLE'}")
print("-" * 90)

for a in aug20_acts:
    ts = a.get("timestamp", 0)
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    t = a.get("type", "")
    s = a.get("side", "")
    px = float(a.get("price") or 0)
    sz = float(a.get("size") or 0)
    usdc = float(a.get("usdcSize") or (px * sz))
    title = a.get("title", "")[:40]
    print(f"{dt_str:<19} | {t:<6} | ${px:<5.2f} | {sz:<7.2f} | ${usdc:<11.2f} | {title}")

print("="*90)
