from py_clob_client_v2 import ClobClient, ApiCreds
from dotenv import load_dotenv
import os
import requests

load_dotenv("scalper_bailout_deploy/.env")

CLOB_HOST = "https://clob.polymarket.com"

# Check sampling market tick size and min size
r = requests.get(f"{CLOB_HOST}/sampling-markets").json()
data = r.get("data", [])
for m in data[:3]:
    print("Market:", m.get("condition_id"), "Min order size:", m.get("min_order_size"), "Min tick size:", m.get("min_tick_size"))

# Also test sampling 5m market
r_ev = requests.get("https://gamma-api.polymarket.com/events?slug=btc-updown-5m-1787429400").json()
if r_ev:
    mkt = r_ev[0]["markets"][0]
    tid = eval(mkt.get("clobTokenIds"))[0]
    r_book = requests.get(f"{CLOB_HOST}/book?token_id={tid}").json()
    print("Market asks:", r_book.get("asks", [])[:2])
