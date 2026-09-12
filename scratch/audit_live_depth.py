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
print(f"📊 LIVE POLYMARKET CLOB LIQUIDITY DEPTH AUDIT: {slug}")
print("="*90)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
if r and r[0].get("markets"):
    mkt = r[0]["markets"][0]
    tids = json.loads(mkt.get("clobTokenIds", "[]"))
    up_id, dn_id = tids[0], tids[1]
    
    r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_id}", timeout=2).json()
    r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_id}", timeout=2).json()
    
    print("\n🟢 UP TOKEN ORDER BOOK DEPTH:")
    up_asks = r_up.get("asks", [])
    total_up_usd = 0.0
    for a in sorted(up_asks, key=lambda x: float(x["price"])):
        px = float(a["price"])
        sz = float(a["size"])
        usd = px * sz
        total_up_usd += usd
        print(f"  Ask @ ${px:.4f} | Size: {sz:>8.2f} shares | Available Liquidity: ${usd:>8.2f} USDC")
    print(f"  👉 Total UP Sell Liquidity on Book: ${total_up_usd:.2f} USDC")

    print("\n🔴 DOWN TOKEN ORDER BOOK DEPTH:")
    dn_asks = r_dn.get("asks", [])
    total_dn_usd = 0.0
    for a in sorted(dn_asks, key=lambda x: float(x["price"])):
        px = float(a["price"])
        sz = float(a["size"])
        usd = px * sz
        total_dn_usd += usd
        print(f"  Ask @ ${px:.4f} | Size: {sz:>8.2f} shares | Available Liquidity: ${usd:>8.2f} USDC")
    print(f"  👉 Total DOWN Sell Liquidity on Book: ${total_dn_usd:.2f} USDC")

print("="*90)
