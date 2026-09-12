import requests
import json
import time
import sys
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

print("="*105)
print("🔍 7-DAY EMPIRICAL TRADE AUDIT: ANALYZING EXACT HISTORICAL FILLS ON WINNING TOKENS")
print("="*105)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# Sample 100 historical 5-minute Bitcoin markets across the past 7 days
now_ts = int(time.time() // 300) * 300
sample_timestamps = [now_ts - (i * 300 * 10) for i in range(1, 101)]

print(f"Auditing 100 historical 5m Bitcoin markets across 7 days ({len(sample_timestamps)} windows)...\n")

def audit_market(ts):
    slug = f"btc-updown-5m-{ts}"
    w_s = ts
    w_e = ts + 300
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r or not r[0].get("markets"): return None
        mkt = r[0]["markets"][0]
        
        clob_ids = json.loads(mkt.get("clobTokenIds") or "[]")
        out_prices = json.loads(mkt.get("outcomePrices") or "[]")
        if not out_prices or len(out_prices) < 2: return None
        
        # Identify winning token
        p0 = float(out_prices[0])
        p1 = float(out_prices[1])
        if p0 == p1: return None # unclosed or tie
        winner_idx = 0 if p0 > p1 else 1
        winning_tid = clob_ids[winner_idx]
        winning_outcome = "UP" if winner_idx == 0 else "DOWN"
        
        # Query trade logs for the winning token
        t_res = requests.get(f"{DATA_HOST}/trades?asset_id={winning_tid}&limit=200", timeout=4).json()
        
        market_trades = []
        for t in t_res:
            trade_t = int(t.get("timestamp", 0))
            if w_s <= trade_t <= w_e:
                offset_s = trade_t - w_s
                price = float(t.get("price", 0))
                size = float(t.get("size", 0))
                side = t.get("side")
                market_trades.append({
                    "offset_s": offset_s,
                    "price": price,
                    "size": size,
                    "side": side,
                    "val": price * size
                })
        return {
            "slug": slug,
            "winner": winning_outcome,
            "trades": market_trades
        }
    except Exception:
        return None

results = []
with ThreadPoolExecutor(max_workers=10) as executor:
    for res in executor.map(audit_market, sample_timestamps):
        if res and res["trades"]:
            results.append(res)

print(f"Successfully pulled verified trade history from {len(results)} closed 5-minute markets.\n")

# Define time buckets:
# 1. Minute 0 (0s - 60s)
# 2. Minute 1 (60s - 120s)
# 3. Minute 2 (120s - 180s)
# 4. Minute 3 (180s - 240s)
# 5. Minute 4 (240s - 288s)
# 6. T-12s (288s - 300s)

buckets = [
    ("Minute 0", 0, 60),
    ("Minute 1", 60, 120),
    ("Minute 2", 120, 180),
    ("Minute 3", 180, 240),
    ("Minute 4.0-4.8", 240, 288),
    ("T-12s Snipe", 288, 300)
]

bucket_stats = {
    b[0]: {
        "trades": 0,
        "buys": 0,
        "shares": 0.0,
        "volume": 0.0,
        "prices": []
    } for b in buckets
}

total_analyzed = 0
for r in results:
    for t in r["trades"]:
        off = t["offset_s"]
        for b_name, b_min, b_max in buckets:
            if b_min <= off < b_max or (b_max == 300 and off >= 288):
                bucket_stats[b_name]["trades"] += 1
                if t["side"] == "BUY":
                    bucket_stats[b_name]["buys"] += 1
                bucket_stats[b_name]["shares"] += t["size"]
                bucket_stats[b_name]["volume"] += t["val"]
                bucket_stats[b_name]["prices"].append(t["price"])
                total_analyzed += 1
                break

print(f"Total Trade Fills Analyzed on Winning Outcome: {total_analyzed}\n")
print(f"{'Time Bucket':<16} | {'Seconds':<10} | {'Total Fills':<12} | {'BUY Orders':<12} | {'Shares Traded':<18} | {'Volume (USDC)':<16} | {'Avg Price':<10} | {'Price Range'}")
print("-" * 115)

for b_name, b_min, b_max in buckets:
    st = bucket_stats[b_name]
    cnt = st["trades"]
    buys = st["buys"]
    sh = st["shares"]
    vol = st["volume"]
    avg_p = (sum(st["prices"]) / len(st["prices"])) if st["prices"] else 0.0
    min_p = min(st["prices"]) if st["prices"] else 0.0
    max_p = max(st["prices"]) if st["prices"] else 0.0
    
    range_str = f"${min_p:.3f} - ${max_p:.3f}" if cnt > 0 else "N/A"
    sec_str = f"{b_min}s - {b_max}s"
    
    print(f"{b_name:<16} | {sec_str:<10} | {cnt:<12} | {buys:<12} | {sh:<16,.1f} sh | ${vol:<14,.2f} | ${avg_p:<8.3f} | {range_str}")

print("="*115)
