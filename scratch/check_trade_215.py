import os
import sys
import json
import time
import datetime
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("scalper_bailout_deploy/.env")

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS", "")

print("="*100)
print("🔍 AUDITING AUGUST 22, 2:15PM-2:20PM ET TRADE (18:15-18:20 UTC)")
print("="*100)

# Check recent user activity directly
r_act = requests.get(f"{DATA_HOST}/activity?user={POLYMARKET_ADDRESS}&limit=10").json()

print(f"{'#':<3} | {'TIMESTAMP (UTC)':<19} | {'TYPE':<6} | {'SIDE':<5} | {'PRICE':<6} | {'SHARES':<10} | {'USDC AMOUNT':<12} | {'TITLE'}")
print("-"*100)
for i, a in enumerate(r_act):
    ts = a.get("timestamp", 0)
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    a_type = a.get("type", "")
    side = a.get("side", "")
    px = float(a.get("price") or 0)
    sz = float(a.get("size") or 0)
    usdc = float(a.get("usdcSize") or (px * sz))
    title = a.get("title", "")
    print(f"{i+1:<3} | {dt_str:<19} | {a_type:<6} | {side:<5} | ${px:<5.2f} | {sz:<10.2f} | ${usdc:<11.2f} | {title}")

# Check resolution of that market
r_ev = requests.get(f"{GAMMA_HOST}/events?limit=10&closed=true").json()
for ev in r_ev:
    if "August 22, 2:15PM" in ev.get("title", "") or "2:15PM" in str(ev):
        m = ev["markets"][0]
        print(f"\nMarket Title: {m.get('question')}")
        print(f"Outcome Prices: {m.get('outcomePrices')}")
        pxs = json.loads(m.get("outcomePrices", "[]"))
        if pxs:
            if float(pxs[0]) >= 0.99: print("🏆 Winner was: UP ($1.00 payout!)")
            elif float(pxs[1]) >= 0.99: print("🏆 Winner was: DOWN ($1.00 payout!)")
