import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"
POLYMARKET_ADDRESS = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"

r_act = requests.get(f"{DATA_HOST}/activity?user={POLYMARKET_ADDRESS}&limit=10").json()

print("="*90)
print("LATEST ON-CHAIN ACTIVITY FOR WALLET:")
print("="*90)
for a in r_act:
    ts = a.get("timestamp", 0)
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    t = a.get("type", "")
    s = a.get("side", "")
    px = float(a.get("price") or 0)
    sz = float(a.get("size") or 0)
    usdc = float(a.get("usdcSize") or (px * sz))
    title = a.get("title", "")
    print(f"{dt_str} | {t:<6} | {s:<4} | ${px:<5.2f} | {sz:<7.2f} sh | ${usdc:<6.2f} | {title}")

# Also check resolution of 4:10PM-4:15PM
r_ev = requests.get(f"{GAMMA_HOST}/events?slug=btc-updown-5m-1787429400").json()
if r_ev:
    m = r_ev[0]["markets"][0]
    print(f"\nMarket: {m.get('question')}")
    print(f"Outcome Prices: {m.get('outcomePrices')}")
