import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

print("="*90)
print("🔍 EMPIRICAL ORDER BOOK DEPTH & WORST-CASE LOSS AUDIT")
print("="*90)

now = time.time()
w_s = int(now // 300) * 300
slugs = [f"btc-updown-5m-{w_s}", f"btc-updown-5m-{w_s - 300}"]

for slug in slugs:
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
        if not r or not r[0].get("markets"): continue
        mkt = r[0]["markets"][0]
        tids = json.loads(mkt.get("clobTokenIds") or "[]")
        
        print(f"\n📊 MARKET: {mkt.get('question', slug)}")
        
        for idx, name in enumerate(["UP", "DOWN"]):
            if idx >= len(tids): continue
            tid = tids[idx]
            r_b = requests.get(f"{CLOB_HOST}/book?token_id={tid}").json()
            bids = r_b.get("bids", [])
            asks = r_b.get("asks", [])
            
            best_bid = float(max(bids, key=lambda b: float(b["price"]))["price"]) if bids else 0.0
            best_ask = float(min(asks, key=lambda a: float(a["price"]))["price"]) if asks else 0.0
            
            # Calculate total liquidity (USDC) available at >= 0.95, >= 0.90, >= 0.80
            liq_95 = sum(float(b["size"]) * float(b["price"]) for b in bids if float(b["price"]) >= 0.95)
            liq_90 = sum(float(b["size"]) * float(b["price"]) for b in bids if float(b["price"]) >= 0.90)
            liq_all = sum(float(b["size"]) * float(b["price"]) for b in bids)
            
            print(f"  [{name}] Best Ask: ${best_ask:.4f} | Best Bid: ${best_bid:.4f}")
            print(f"       • Bid Liquidity >= $0.95: ${liq_95:,.2f} USDC")
            print(f"       • Bid Liquidity >= $0.90: ${liq_90:,.2f} USDC")
            print(f"       • Total Bid Liquidity:    ${liq_all:,.2f} USDC")
    except Exception as e:
        print("Error:", e)

print("\n" + "="*90)
