import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
WALLET = "0x89B489569F1B2384ee02E958444aF6091219bfe9"

print("="*90)
print(f"🔍 AUDITING DEPOSITS, TRANSFERS & REDEMPTIONS FOR WALLET: {WALLET}")
print("="*90)

# Check activity endpoint
r_act = requests.get(f"{DATA_HOST}/activity?user={WALLET}&limit=25", timeout=5).json()
for a in r_act:
    ts = a.get("timestamp", 0)
    dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%m/%d %H:%M:%S UTC")
    atype = a.get("type", "")
    side = a.get("side", "")
    sz = float(a.get("size", 0))
    usdc_sz = float(a.get("usdcSize", 0))
    title = a.get("title", "")
    print(f"[{dt}] {atype:<8} | {side:<4} | ${usdc_sz:<8.4f} ({sz:.2f} sh) | {title}")

print("="*90)
