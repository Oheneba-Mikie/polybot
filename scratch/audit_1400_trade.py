import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
slug = "btc-updown-5m-1787666400"

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
print("="*90)
print(f"AUDITING 14:00 - 14:05 UTC CANDLE ({slug}):")
print("="*90)
if r and r[0].get("markets"):
    mkt = r[0]["markets"][0]
    print("Question:", mkt.get("question"))
    print("Resolution Outcome Prices:", mkt.get("outcomePrices"))
    print("Closed:", mkt.get("closed"))
print("="*90)
