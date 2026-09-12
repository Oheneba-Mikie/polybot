import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# Calculate current 5m candle slug
now = time.time()
w_s = int(now // 300) * 300
slug = f"btc-updown-5m-{w_s}"

print("="*95)
print(f"🔍 LIVE 5-MINUTE ORDER BOOK DEPTH & SPREAD AUDIT FOR: {slug}")
print("="*95)

try:
    r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
    if r and r[0].get("markets"):
        mkt = r[0]["markets"][0]
        clob_ids = json.loads(mkt.get("clobTokenIds") or "[]")
        outs = json.loads(mkt.get("outcomes") or "[]")
        print(f"Market Title: {mkt.get('question')}")
        
        for idx, tid in enumerate(clob_ids):
            out_name = outs[idx] if idx < len(outs) else f"Token {idx}"
            b = requests.get(f"{CLOB_HOST}/book", params={"token_id": tid}, timeout=3).json()
            bids = b.get("bids", [])
            asks = b.get("asks", [])
            
            sorted_bids = sorted(bids, key=lambda x: float(x["price"]), reverse=True)
            sorted_asks = sorted(asks, key=lambda x: float(x["price"]))
            
            best_bid = sorted_bids[0]["price"] if sorted_bids else "0.00"
            best_bid_sz = sorted_bids[0]["size"] if sorted_bids else "0.0"
            best_ask = sorted_asks[0]["price"] if sorted_asks else "None"
            best_ask_sz = sorted_asks[0]["size"] if sorted_asks else "0.0"
            
            total_ask_liquidity = sum(float(a["size"]) * float(a["price"]) for a in sorted_asks)
            
            print(f"\n  🎯 [{out_name.upper()} Outcome Book Depth]:")
            print(f"     • Best Bid: ${best_bid} ({best_bid_sz} shares)")
            print(f"     • Best Ask: ${best_ask} ({best_ask_sz} shares)")
            print(f"     • Spread:   ${float(best_ask) - float(best_bid):.3f}" if best_ask != "None" else "Spread: N/A")
            print(f"     • Total Order Book Depth: ${total_ask_liquidity:,.2f} USDC across {len(asks)} ask levels")
except Exception as e:
    print("Error querying live market:", e)

print("="*95)
