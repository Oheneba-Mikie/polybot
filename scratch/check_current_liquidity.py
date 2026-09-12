import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

now = time.time()
cur_w_s = int(now // 300) * 300
slug = f"btc-updown-5m-{cur_w_s}"

print("="*90)
print(f"ORDER BOOK SNAPSHOT FOR CURRENT ACTIVE CANDLE: {slug}")
print("="*90)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
if r and r[0].get("markets"):
    mkt = r[0]["markets"][0]
    tids = json.loads(mkt.get("clobTokenIds", "[]"))
    up_id, dn_id = tids[0], tids[1]
    
    r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_id}", timeout=2).json()
    r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_id}", timeout=2).json()
    
    print("UP Token Asks:", r_up.get("asks", [])[:5])
    print("UP Token Bids:", r_up.get("bids", [])[:5])
    print("-" * 90)
    print("DOWN Token Asks:", r_dn.get("asks", [])[:5])
    print("DOWN Token Bids:", r_dn.get("bids", [])[:5])

print("="*90)
