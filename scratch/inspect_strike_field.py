import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
slug = "btc-updown-5m-1787662200"

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
print("="*90)
print("RAW GAMMA EVENT MARKET DATA:")
print("="*90)
if r and r[0].get("markets"):
    mkt = r[0]["markets"][0]
    print("Question:", mkt.get("question"))
    print("Description:", mkt.get("description"))
    print("GroupItemTitle:", mkt.get("groupItemTitle"))
    print("Market Title:", mkt.get("title"))
print("="*90)
