import sys
import json
import time
import requests

sys.stdout.reconfigure(encoding='utf-8')

CLOB_HOST = "https://clob.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"

now = time.time()
w_s = int(now // 300) * 300

# Check current and next 2 windows
slugs = [f"btc-updown-5m-{w_s}", f"btc-updown-5m-{w_s+300}"]

for slug in slugs:
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
        if not r or not r[0].get("markets"):
            continue
        mkt = r[0]["markets"][0]
        tids = json.loads(mkt.get("clobTokenIds") or "[]")
        outs = [str(o).upper() for o in json.loads(mkt.get("outcomes") or "[]")]
        
        print("="*80)
        print(f"📌 Market: {mkt.get('question')} ({slug})")
        print("="*80)
        
        for idx, tid in enumerate(tids):
            name = outs[idx] if idx < len(outs) else f"Token-{idx}"
            r_book = requests.get(f"{CLOB_HOST}/book?token_id={tid}").json()
            bids = r_book.get("bids", [])
            asks = r_book.get("asks", [])
            
            sorted_bids = sorted(bids, key=lambda b: float(b["price"]), reverse=True)
            sorted_asks = sorted(asks, key=lambda a: float(a["price"]))
            
            best_bid = sorted_bids[0] if sorted_bids else None
            best_ask = sorted_asks[0] if sorted_asks else None
            
            print(f"\n👉 [{name}] Best Ask: ${float(best_ask['price']):.2f} ({best_ask['size']} sh)" if best_ask else f"\n👉 [{name}] No Asks")
            print(f"   [{name}] Top 5 Live Bids on Book (People waiting to buy right now):")
            for b_i, b in enumerate(sorted_bids[:5]):
                px = float(b['price'])
                sz = float(b['size'])
                print(f"      Bid #{b_i+1}: Price ${px:.2f} | Depth: {sz:.2f} shares (${px*sz:.2f} cash available)")
    except Exception as e:
        print(f"Error checking {slug}: {e}")
