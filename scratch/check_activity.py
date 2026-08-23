import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
WALLET = "0x89B489569F1B2384ee02E958444aF6091219bfe9"

print("="*90)
print(f"🔍 COMPLETE ACTIVITY LOG FOR WALLET: {WALLET}")
print("="*90)

r = requests.get(f"{DATA_HOST}/activity?user={WALLET}&limit=30", timeout=5).json()
for a in r:
    ts_sec = a.get("timestamp", 0)
    dt = datetime.datetime.fromtimestamp(ts_sec, datetime.timezone.utc).strftime("%H:%M:%S")
    atype = a.get("type", "")
    side = a.get("side", "")
    sz = float(a.get("size", 0))
    usdc_sz = float(a.get("usdcSize", 0))
    px = float(a.get("price", 0))
    title = a.get("title", "")[:35]
    print(f"[{dt}] {atype:<6} | {side:<4} | {sz:<6.2f} sh (${usdc_sz:<5.2f}) @ ${px:.4f} | {title}")

print("="*90)
