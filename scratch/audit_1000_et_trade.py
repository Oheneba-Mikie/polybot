import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST  = "https://data-api.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# 10:00 AM - 10:05 AM ET on August 26 is 14:00 - 14:05 UTC
w_s = 1787752800 # 14:00 UTC
slug = f"btc-updown-5m-{w_s}"
user_addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8" # Proxy wallet

print("="*95)
print(f"📊 FORENSIC AUDIT: 10:00 AM - 10:05 AM ET (14:00 - 14:05 UTC) CANDLE: {slug}")
print("="*95)

# 1. Fetch our wallet's trades during this window
r_trades = requests.get(f"{DATA_HOST}/trades?user={user_addr}&limit=10").json()
print("📁 WALLET TRADES IN THIS TIMEFRAME:")
found_trade = None
for t in r_trades:
    ts = t.get("timestamp", 0)
    dt_utc = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M:%S UTC")
    dt_et = datetime.datetime.fromtimestamp(ts - 4*3600, datetime.timezone.utc).strftime("%I:%M:%S %p ET")
    out = t.get("outcome")
    sz = float(t.get("size", 0))
    px = float(t.get("price", 0))
    side = t.get("side")
    title = t.get("title", "")
    print(f"  [{dt_et} | {dt_utc}] {side} {sz:.2f} shares of {out} @ ${px:.4f} (Cost: ${sz*px:.2f}) | Market: {title}")
    if "10:00" in dt_et or "10:01" in dt_et or "10:02" in dt_et or "10:03" in dt_et or "10:04" in dt_et or "14:0" in dt_utc:
        found_trade = t

# 2. Query the market details and order book behavior
r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
if r_evt and r_evt[0].get("markets"):
    mkt = r_evt[0]["markets"][0]
    q = mkt.get("question")
    prices = json.loads(mkt.get("outcomePrices") or "[]")
    tids = json.loads(mkt.get("clobTokenIds", "[]"))
    print(f"\n📁 Market Details: {q}")
    print(f"   Outcome Prices: {prices}")
    print(f"   Tokens: UP={tids[0]}, DOWN={tids[1]}")

print("="*95)
