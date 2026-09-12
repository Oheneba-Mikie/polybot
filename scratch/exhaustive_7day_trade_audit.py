import requests
import json
import time
import datetime
import sys
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

print("="*115)
print("🔍 EXHAUSTIVE 7-DAY EMPIRICAL ON-CHAIN TRADE AUDIT ACROSS 100 HISTORICAL 5-MINUTE MARKETS")
print("="*115)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# Sample 100 markets across 7 days
now_ts = int(time.time() // 300) * 300
sample_timestamps = [now_ts - (i * 300 * 10) for i in range(1, 101)]

def audit_single_market(ts):
    slug = f"btc-updown-5m-{ts}"
    w_s = ts
    w_e = ts + 300
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r or not r[0].get("markets"): return None
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        out_prices = json.loads(mkt.get("outcomePrices") or "[]")
        if not out_prices or len(out_prices) < 2: return None
        
        # Determine actual winning side
        p0 = float(out_prices[0])
        p1 = float(out_prices[1])
        if p0 == p1: return None
        winner_side = "UP" if p0 > p1 else "DOWN"
        
        # Fetch verified trades for this market conditionId
        tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=200", timeout=4).json()
        if not tr or not isinstance(tr, list): return None
        
        market_fills = []
        for t in tr:
            trade_ts = t.get("timestamp", 0)
            side = str(t.get("side", "")).upper()
            outcome = str(t.get("outcome", "")).upper()
            price = float(t.get("price", 0))
            size = float(t.get("size", 0))
            
            # Check if trade happened inside candle
            if w_s <= trade_ts <= w_e:
                offset_s = trade_ts - w_s
                is_winner = (outcome == winner_side and side == "BUY")
                market_fills.append({
                    "offset_s": offset_s,
                    "side": side,
                    "outcome": outcome,
                    "is_winner_buy": is_winner,
                    "price": price,
                    "size": size,
                    "val": price * size
                })
        return {
            "slug": slug,
            "winner": winner_side,
            "fills": market_fills
        }
    except Exception:
        return None

print(f"Fetching and parsing real on-chain trade fills from 100 historical 5m markets...\n")

results = []
with ThreadPoolExecutor(max_workers=12) as executor:
    for res in executor.map(audit_single_market, sample_timestamps):
        if res and res["fills"]:
            results.append(res)

print(f"Successfully audited {len(results)} historical 5-minute markets.\n")

# Aggregate by time intervals inside the 5-minute candle
intervals = [
    ("Minute 0:00 - 1:00", 0, 60),
    ("Minute 1:00 - 2:00", 60, 120),
    ("Minute 2:00 - 3:00", 120, 180),
    ("Minute 3:00 - 4:00", 180, 240),
    ("Minute 4:00 - 4:40", 240, 280),
    ("Minute 4:40 - 4:48 (T-20s to T-12s)", 280, 288),
    ("Minute 4:48 - 5:00 (Final T-12s)", 288, 300)
]

stats = {
    iv[0]: {
        "total_trades": 0,
        "winner_buys": 0,
        "loser_buys": 0,
        "shares_traded": 0.0,
        "total_usdc": 0.0,
        "prices": [],
        "sizes": []
    } for iv in intervals
}

total_fills = 0
for r in results:
    for f in r["fills"]:
        off = f["offset_s"]
        for iv_name, s_start, s_end in intervals:
            if s_start <= off < s_end or (s_end == 300 and off >= 288):
                st = stats[iv_name]
                st["total_trades"] += 1
                if f["is_winner_buy"]:
                    st["winner_buys"] += 1
                elif f["side"] == "BUY":
                    st["loser_buys"] += 1
                st["shares_traded"] += f["size"]
                st["total_usdc"] += f["val"]
                st["prices"].append(f["price"])
                st["sizes"].append(f["size"])
                total_fills += 1
                break

print(f"TOTAL VERIFIED ON-CHAIN TRADE FILLS ANALYZED: {total_fills}\n")
print(f"{'Candle Time Window':<36} | {'Fills':<8} | {'Win Buys':<10} | {'Shares Filled':<18} | {'Total USDC':<14} | {'Avg Price':<10} | {'Price Range'}")
print("-" * 115)

for iv_name, s_start, s_end in intervals:
    st = stats[iv_name]
    cnt = st["total_trades"]
    wb = st["winner_buys"]
    sh = st["shares_traded"]
    val = st["total_usdc"]
    avg_p = (sum(st["prices"]) / len(st["prices"])) if st["prices"] else 0.0
    min_p = min(st["prices"]) if st["prices"] else 0.0
    max_p = max(st["prices"]) if st["prices"] else 0.0
    range_str = f"${min_p:.2f} - ${max_p:.2f}" if cnt > 0 else "N/A"
    
    print(f"{iv_name:<36} | {cnt:<8} | {wb:<10} | {sh:<16,.1f} sh | ${val:<12,.2f} | ${avg_p:<8.3f} | {range_str}")

print("="*115)
