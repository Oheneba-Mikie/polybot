import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"

slug = "btc-updown-5m-1787752800"
r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
mkt = r_evt[0]["markets"][0]
cid = mkt.get("conditionId")

r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=10").json()
print("Sample Trades from 1787752800:")
for t in r_tr:
    print(t)
