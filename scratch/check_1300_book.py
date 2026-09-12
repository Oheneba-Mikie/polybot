import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

ts = 1787662800 # 13:00 UTC
slug = f"btc-updown-5m-{ts}"

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
if r and r[0].get("markets"):
    mkt = r[0]["markets"][0]
    tids = json.loads(mkt.get("clobTokenIds", "[]"))
    up_id, dn_id = tids[0], tids[1]
    
    r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_id}", timeout=2).json()
    r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_id}", timeout=2).json()
    
    up_asks = [float(a['price']) for a in r_up.get("asks", [])]
    dn_asks = [float(a['price']) for a in r_dn.get("asks", [])]
    
    print("="*90)
    print(f"CANDLE: {slug} (13:00 - 13:05 UTC)")
    print(f"UP Asks:   {up_asks[:5]}")
    print(f"DOWN Asks: {dn_asks[:5]}")
    print("="*90)
