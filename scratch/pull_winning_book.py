import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

now = time.time()
cur_w_s = int(now // 300) * 300
slug = f"btc-updown-5m-{cur_w_s}"

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
mkt = r[0]["markets"][0]
clob_token_ids = json.loads(mkt.get("clobTokenIds", "[]"))
dn_id = clob_token_ids[1]

print("="*95)
print(f"🔍 LIVE MILLISECOND ORDER BOOK ON WINNING TOKEN (DOWN):")
print("="*95)
print(f"{'Timestamp (UTC.ms)':<22} | {'Top 3 Bids (Price:Shares)':<42} | {'Top 3 Asks (Price:Shares)'}")
print("-" * 95)

for i in range(10):
    t_now = time.time()
    dt = datetime.datetime.fromtimestamp(t_now, datetime.timezone.utc)
    ms_str = dt.strftime("%H:%M:%S") + f".{int(dt.microsecond / 1000):03d}"
    
    try:
        r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_id}", timeout=2).json()
        bids = r_dn.get("bids", [])[:3]
        asks = r_dn.get("asks", [])[:3]
        
        bids_str = ", ".join([f"${float(b['price']):.2f}:{float(b['size']):.0f}sh" for b in bids])
        asks_str = ", ".join([f"${float(a['price']):.2f}:{float(a['size']):.0f}sh" for a in asks])
        
        print(f"[{ms_str}] | {bids_str:<42} | {asks_str}")
    except Exception as e:
        print(f"[{ms_str}] Error: {e}")
        
    time.sleep(0.3)

print("="*95)
