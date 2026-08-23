import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
WALLET = "0x89B489569F1B2384ee02E958444aF6091219bfe9"

# 12:35 UTC candle (1787488500)
ts = 1787488500
slug = f"btc-updown-5m-{ts}"

print("="*85)
print(f"🔍 CHECKING 8:35 AM - 8:40 AM ET CANDLE RESOLUTION ({slug}):")
print("="*85)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
if r and r[0].get("markets"):
    mkt = r[0]["markets"][0]
    cid = mkt.get("conditionId")
    question = mkt.get("question")
    prices = json.loads(mkt.get("outcomePrices", "[]"))
    resolved = mkt.get("resolved")
    closed = mkt.get("closed")
    print(f"Question: {question}")
    print(f"Condition ID: {cid}")
    print(f"Resolved: {resolved} | Closed: {closed}")
    print(f"Final Outcome Prices: {prices}")

# Check redeemable positions on Data API
r_red = requests.get(f"{DATA_HOST}/positions?user={WALLET}&sizeThreshold=0.01", timeout=5).json()
print(f"\nAll Positions on User Wallet ({len(r_red)} found):")
for p in r_red:
    title = p.get("title", "")
    sz = float(p.get("size", 0))
    val = float(p.get("currentValue", 0))
    red = p.get("redeemable", False)
    print(f"- {title} | Size: {sz:.2f} shares | Value: ${val:.2f} | Redeemable: {red}")

print("="*85)
