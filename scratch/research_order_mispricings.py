import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

print("="*95)
print("🔬 24-HOUR EMPIRICAL RESEARCH: ORDER BOOK MISPRICINGS & SPREAD DYNAMICS (UP + DOWN != 1.00)")
print("="*95)

now = time.time()
cur_w_s = int(now // 300) * 300

# Sample 50 completed 5-minute candles across 24 hours
sample_slugs = []
for i in range(1, 60):
    w_s = cur_w_s - (i * 300 * 4) # Step every 20 minutes across 24h
    sample_slugs.append(f"btc-updown-5m-{w_s}")

total_analyzed = 0
arb_occurrences = 0
mispricing_pairs = {}
trade_spread_sums = []
all_trades = []

print("Analyzing historical market order prints & trade logs across 24 hours...")

for slug in sample_slugs[:25]:
    try:
        r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
        if not r_evt or not r_evt[0].get("markets"): continue
        mkt = r_evt[0]["markets"][0]
        cid = mkt.get("conditionId")
        q = mkt.get("question")
        
        # Get historical trades from Data API
        r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=150", timeout=3).json()
        if not r_tr: continue
        total_analyzed += 1
        
        # Group trades by timestamp second
        trades_by_sec = {}
        for t in r_tr:
            ts = t.get("timestamp", 0)
            out = str(t.get("outcome", "")).upper()
            px = float(t.get("price", 0))
            sz = float(t.get("size", 0))
            if ts not in trades_by_sec:
                trades_by_sec[ts] = {"UP": [], "DOWN": []}
            if "UP" in out or "YES" in out:
                trades_by_sec[ts]["UP"].append((px, sz))
            else:
                trades_by_sec[ts]["DOWN"].append((px, sz))
        
        # Detect cross-token pricing pairs and sum deviations
        for ts, d in trades_by_sec.items():
            if d["UP"] and d["DOWN"]:
                for up_p, up_s in d["UP"]:
                    for dn_p, dn_s in d["DOWN"]:
                        pair_sum = round(up_p + dn_p, 3)
                        trade_spread_sums.append(pair_sum)
                        pair_key = f"{up_p:.2f} + {dn_p:.2f} = {pair_sum:.2f}"
                        mispricing_pairs[pair_key] = mispricing_pairs.get(pair_key, 0) + 1
                        if pair_sum < 0.995 or pair_sum > 1.005:
                            arb_occurrences += 1
    except Exception:
        continue

print(f"\n📊 24-HOUR ANALYSIS RESULTS ({total_analyzed} Markets Analyzed):")
print(f"Total Concurrent Dual-Side Prints Analyzed: {len(trade_spread_sums)}")

# Sort top occurring price pairs
sorted_pairs = sorted(mispricing_pairs.items(), key=lambda x: x[1], reverse=True)

print("\n🏆 MOST FREQUENT ORDER PAIRS OCCURRING ON POLYMARKET:")
for pair, count in sorted_pairs[:15]:
    pct = (count / len(trade_spread_sums)) * 100 if trade_spread_sums else 0
    print(f"  • {pair:<28} | Occurrences: {count:>4} ({pct:>5.1f}%)")

# Test live active market order books right now
print("\n" + "="*95)
print("⚡ LIVE REAL-TIME ACTIVE MARKET BOOK AUDIT:")
cur_active_slug = f"btc-updown-5m-{cur_w_s}"
r_live = requests.get(f"{GAMMA_HOST}/events?slug={cur_active_slug}", timeout=3).json()
if r_live and r_live[0].get("markets"):
    mkt = r_live[0]["markets"][0]
    tids = json.loads(mkt.get("clobTokenIds", "[]"))
    up_id, dn_id = tids[0], tids[1]
    r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_id}").json()
    r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_id}").json()
    
    up_bids = [float(b["price"]) for b in r_up.get("bids", [])]
    up_asks = [float(a["price"]) for a in r_up.get("asks", [])]
    dn_bids = [float(b["price"]) for b in r_dn.get("bids", [])]
    dn_asks = [float(a["price"]) for a in r_dn.get("asks", [])]
    
    best_up_bid = max(up_bids) if up_bids else 0.0
    best_up_ask = min(up_asks) if up_asks else 1.0
    best_dn_bid = max(dn_bids) if dn_bids else 0.0
    best_dn_ask = min(dn_asks) if dn_asks else 1.0
    
    bid_sum = best_up_bid + best_dn_bid
    ask_sum = best_up_ask + best_dn_ask
    
    print(f"Active Market: {cur_active_slug}")
    print(f"🟢 UP:   Top Bid = ${best_up_bid:.4f} | Best Ask = ${best_up_ask:.4f}")
    print(f"🔴 DOWN: Top Bid = ${best_dn_bid:.4f} | Best Ask = ${best_dn_ask:.4f}")
    print(f"📊 Sum of Top BIDS (UP + DOWN): ${bid_sum:.4f} (Haircut / Discount = ${1.00 - bid_sum:.4f})")
    print(f"📊 Sum of Best ASKS (UP + DOWN): ${ask_sum:.4f} (Market Maker Spread = ${ask_sum - 1.00:.4f})")

print("="*95)
