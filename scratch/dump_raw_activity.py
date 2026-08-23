import os
import sys
import json
import datetime
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("scalper_bailout_deploy/.env")

DATA_HOST = "https://data-api.polymarket.com"
POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS", "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8")

print("="*100)
print(f"🔍 RAW POLYMARKET BLOCKCHAIN ACTIVITY FEED FOR WALLET: {POLYMARKET_ADDRESS}")
print("="*100)

url = f"{DATA_HOST}/activity?user={POLYMARKET_ADDRESS}&limit=35"
r = requests.get(url, timeout=10)
acts = r.json()

print(f"Fetched {len(acts)} total activity records from {DATA_HOST}.\n")

print(f"{'#':<3} | {'TIMESTAMP (UTC)':<19} | {'ACTION':<7} | {'SIDE':<5} | {'PRICE':<6} | {'SHARES':<7} | {'USDC':<7} | {'TRANSACTION TITLE'}")
print("="*95)

for i, a in enumerate(acts):
    ts = a.get("timestamp", 0)
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    a_type = a.get("type", "")
    side = a.get("side", "")
    px = float(a.get("price") or 0)
    sz = float(a.get("size") or 0)
    usdc = float(a.get("usdcSize") or (px * sz))
    title = a.get("title", "")
    print(f"{i+1:<3} | {dt_str:<19} | {a_type:<7} | {side:<5} | ${px:<5.2f} | {sz:<7.2f} | ${usdc:<6.2f} | {title}")

# Also let's save the raw json response so there's 100% transparency
with open("scratch/raw_activity_dump.json", "w") as f:
    json.dump(acts, f, indent=2)

print("\nSaved complete raw payload to scratch/raw_activity_dump.json.")
