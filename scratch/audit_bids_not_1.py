import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

print("="*95)
print("🔬 DEEP RESEARCH: DUAL-SIDE BIDS THAT DO NOT ADD TO 1.00 (e.g. 0.85 BID + 0.25 BID = 1.10)")
print("="*95)

now = time.time()
cur_w_s = int(now // 300) * 300

bid_pair_occurrences = {}
bid_sum_distribution = {}

# Analyze the last 30 5-minute candles on Polymarket
for i in range(0, 30):
    w_s = cur_w_s - (i * 300)
    slug = f"btc-updown-5m-{w_s}"
    try:
        r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
        if not r_evt or not r_evt[0].get("markets"): continue
        mkt = r_evt[0]["markets"][0]
        tids = json.loads(mkt.get("clobTokenIds", "[]"))
        up_id, dn_id = tids[0], tids[1]
        
        r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_id}", timeout=2).json()
        r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_id}", timeout=2).json()
        
        up_bids = [float(b["price"]) for b in r_up.get("bids", [])]
        dn_bids = [float(b["price"]) for b in r_dn.get("bids", [])]
        
        # Check all overlapping bid pairs on the book
        for up_b in up_bids[:5]:
            for dn_b in dn_bids[:5]:
                b_sum = round(up_b + dn_b, 2)
                pair_str = f"Bid {up_b:.2f} (UP) + Bid {dn_b:.2f} (DOWN) = {b_sum:.2f}"
                bid_pair_occurrences[pair_str] = bid_pair_occurrences.get(pair_str, 0) + 1
                bid_sum_distribution[b_sum] = bid_sum_distribution.get(b_sum, 0) + 1
    except Exception:
        continue

print(f"\n📊 TOP COMBINED BID PAIRS ON THE BOOKS (UP + DOWN BIDS != 1.00):")
sorted_bids = sorted(bid_pair_occurrences.items(), key=lambda x: x[1], reverse=True)
for pair, count in sorted_bids[:20]:
    print(f"  • {pair:<55} | Count: {count:>3}")

print("\n📊 COMBINED BID SUM DISTRIBUTION:")
for b_sum, count in sorted(bid_sum_distribution.items()):
    print(f"  • Bid Sum = ${b_sum:.2f} | Count: {count:>3}")

print("="*95)
