import requests
import json
import time
import sys
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

print("="*105)
print("🔍 2-WEEK EMPIRICAL TRADE LOG AUDIT: AT WHAT MINUTE & PRICE DO REAL WINNING TRADES ACTUALLY OCCUR?")
print("="*105)

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# 1. Fetch historical 5-minute Bitcoin markets across past 14 days
now_ts = int(time.time() // 300) * 300
# Sample across the last 14 days (14 * 288 = 4032 candles)
# Query 150 closed historical 5m market slugs spaced across 14 days
sample_timestamps = [now_ts - (i * 300 * 20) for i in range(1, 151)] # 150 windows across 14 days

print(f"Querying public trade logs for {len(sample_timestamps)} historical 5-minute Bitcoin markets across the past 14 days...\n")

def audit_market_trades(ts):
    slug = f"btc-updown-5m-{ts}"
    w_s = ts
    w_e = ts + 300
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
        if not r or not r[0].get("markets"): return None
        mkt = r[0]["markets"][0]
        
        clob_ids = json.loads(mkt.get("clobTokenIds") or "[]")
        outs = json.loads(mkt.get("outcomes") or "[]")
        
        # Determine winner from market prices/settlement if closed
        # outcomePrices e.g. ["1", "0"] or ["0", "1"]
        out_prices = json.loads(mkt.get("outcomePrices") or "[]")
        if not out_prices or len(out_prices) < 2: return None
        
        winner_idx = 0 if float(out_prices[0]) > 0.5 else 1
        winning_tid = clob_ids[winner_idx] if winner_idx < len(clob_ids) else None
        
        if not winning_tid: return None
        
        # Query trade fills for the winning outcome token
        t_res = requests.get(f"{CLOB_HOST}/trades", params={"market": winning_tid, "limit": 100}, timeout=3).json()
        trades = t_res.get("data", [])
        
        parsed_trades = []
        for t in trades:
            trade_t = float(t.get("timestamp", 0))
            if w_s <= trade_t <= w_e:
                offset_s = trade_t - w_s # seconds into candle
                minute_bucket = int(offset_s // 60) # Minute 0, 1, 2, 3, 4
                price = float(t.get("price", 0))
                size = float(t.get("size", 0))
                side = t.get("side")
                parsed_trades.append({
                    "offset_s": offset_s,
                    "minute": minute_bucket,
                    "price": price,
                    "size": size,
                    "side": side,
                    "val": price * size
                })
        return {"slug": slug, "trades": parsed_trades}
    except Exception:
        return None

results = []
with ThreadPoolExecutor(max_workers=12) as executor:
    for res in executor.map(audit_market_trades, sample_timestamps):
        if res and res["trades"]:
            results.append(res)

print(f"Successfully retrieved verified trade execution logs from {len(results)} distinct historical 5-minute markets.\n")

# Aggregate statistics by Minute bucket of the candle (Minute 0, 1, 2, 3, 4)
minute_stats = {
    m: {
        "trades_cnt": 0,
        "total_shares": 0.0,
        "total_volume": 0.0,
        "prices": [],
        "sizes": []
    } for m in range(5)
}

total_fills = 0
for r in results:
    for t in r["trades"]:
        m = min(4, max(0, t["minute"]))
        minute_stats[m]["trades_cnt"] += 1
        minute_stats[m]["total_shares"] += t["size"]
        minute_stats[m]["total_volume"] += t["val"]
        minute_stats[m]["prices"].append(t["price"])
        minute_stats[m]["sizes"].append(t["size"])
        total_fills += 1

print(f"Total Individual Trade Fills Analyzed: {total_fills}\n")
print(f"{'Candle Minute':<15} | {'Seconds Range':<16} | {'Actual Fills':<14} | {'Total Shares Traded':<22} | {'Avg Fill Price':<16} | {'Price Range'}")
print("-" * 105)

for m in range(5):
    s_start = m * 60
    s_end = (m + 1) * 60
    st = minute_stats[m]
    cnt = st["trades_cnt"]
    sh = st["total_shares"]
    vol = st["total_volume"]
    avg_p = (sum(st["prices"]) / len(st["prices"])) if st["prices"] else 0.0
    min_p = min(st["prices"]) if st["prices"] else 0.0
    max_p = max(st["prices"]) if st["prices"] else 0.0
    
    range_str = f"${min_p:.3f} - ${max_p:.3f}" if cnt > 0 else "N/A"
    
    print(f"Minute {m:<8} | {s_start:>3}s - {s_end:<4}s     | {cnt:<14} | {sh:<20,.1f} sh | ${avg_p:<14.3f} | {range_str}")

print("="*105)
