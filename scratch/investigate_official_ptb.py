import requests
import json

slug = "btc-updown-5m-1787146800" # 13:40 cycle

print("="*80)
print(f"CHECKING OFFICIAL POLYMARKET PTB SOURCES FOR SLUG: {slug}")
print("="*80)

# 1. Check Polymarket Gamma Market details
r_gamma = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
if r_gamma:
    m = r_gamma[0]["markets"][0]
    print("Market Question:", m.get("question"))
    print("Market Group:", m.get("groupItemThreshold"))
    print("Market eventStartTime:", m.get("eventStartTime"))

# 2. Check Polymarket Price Oracle / Crypto prices API
try:
    r_oracle = requests.get("https://clob.polymarket.com/prices-history?market=...").json()
    print("CLOB prices-history:", r_oracle)
except Exception as e:
    print("CLOB error:", e)

# 3. Check Polymarket Chainlink feed historical query
try:
    # 13:40:00 timestamp = 1787146800
    r_feed = requests.get("https://polymarket.com/api/crypto-prices?symbol=BTC&timestamp=1787146800").json()
    print("Polymarket crypto-prices API:", r_feed)
except Exception as e:
    print("crypto-prices error:", e)
