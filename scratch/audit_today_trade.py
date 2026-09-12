import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# The trade at 12:18:33 UTC:
# Market: Bitcoin Up or Down - August 25, 8:15AM-8:20AM ET (12:15 UTC - 12:20 UTC)
# Timestamp: 1787660100 (or around 12:15 UTC)
now = int(datetime.datetime(2026, 8, 25, 12, 15, 0, tzinfo=datetime.timezone.utc).timestamp())
slug = f"btc-updown-5m-{now}"

print("="*90)
print(f"🎯 AUDITING TODAY'S LIVE 12:18 UTC SNIPE CANDLE: {slug}")
print("="*90)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
if r and r[0].get("markets"):
    mkt = r[0]["markets"][0]
    print(f"Question: {mkt.get('question')}")
    print(f"Outcome Prices (Resolution): {mkt.get('outcomePrices')}")
    print(f"Closed: {mkt.get('closed')} | Resolved: {mkt.get('resolved')}")

print("="*90)
