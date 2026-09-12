import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

CLOB_HOST = "https://clob.polymarket.com"

# Check active token IDs
slug = "btc-updown-5m-1787663400"
r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
mkt = r[0]["markets"][0]
tids = json.loads(mkt.get("clobTokenIds", "[]"))
up_id, dn_id = tids[0], tids[1]

r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_id}").json()
r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_id}").json()

up_bids = sorted([float(b['price']) for b in r_up.get('bids', [])], reverse=True)
up_asks = sorted([float(a['price']) for a in r_up.get('asks', [])])

dn_bids = sorted([float(b['price']) for b in r_dn.get('bids', [])], reverse=True)
dn_asks = sorted([float(a['price']) for a in r_dn.get('asks', [])])

print("="*90)
print(f"CLOB BOOK STRUCTURE FOR CANDLE {slug}:")
print(f"UP   | Best Bid: {up_bids[0] if up_bids else None} | Best Ask: {up_asks[0] if up_asks else None} | All Asks: {up_asks}")
print(f"DOWN | Best Bid: {dn_bids[0] if dn_bids else None} | Best Ask: {dn_asks[0] if dn_asks else None} | All Asks: {dn_asks}")
print("="*90)
