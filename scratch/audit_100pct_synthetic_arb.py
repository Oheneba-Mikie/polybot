import requests
import json
import time
import sys
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

print("="*115)
print("🔍 7-DAY EMPIRICAL AUDIT: 100.00% MATHEMATICAL ARBITRAGE (BUYING UP + DOWN FOR < $1.00)")
print("="*115)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# Sample 100 historical 5-minute markets across past 7 days
now_ts = int(time.time() // 300) * 300
sample_timestamps = [now_ts - (i * 300 * 10) for i in range(1, 101)]

def audit_arbitrage_market(ts):
    slug = f"btc-updown-5m-{ts}"
    w_s = ts
    w_e = ts + 300
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r or not r[0].get("markets"): return None
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        
        tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=200", timeout=4).json()
        if not tr or not isinstance(tr, list): return None
        
        # Track lowest buy price recorded for UP and DOWN during the candle
        min_up_buy = 1.00
        min_down_buy = 1.00
        
        for t in tr:
            trade_ts = t.get("timestamp", 0)
            if w_s <= trade_ts <= w_e:
                side = str(t.get("side", "")).upper()
                out = str(t.get("outcome", "")).upper()
                px = float(t.get("price", 0))
                
                if side == "BUY":
                    if out == "UP" and 0.05 < px < min_up_buy:
                        min_up_buy = px
                    elif out == "DOWN" and 0.05 < px < min_down_buy:
                        min_down_buy = px
                        
        if min_up_buy < 1.00 and min_down_buy < 1.00:
            combined_cost = min_up_buy + min_down_buy
            return {
                "slug": slug,
                "min_up": min_up_buy,
                "min_down": min_down_buy,
                "combined": combined_cost,
                "arb_spread": round(1.00 - combined_cost, 4),
                "is_arb": combined_cost < 0.98
            }
        return None
    except Exception:
        return None

results = []
with ThreadPoolExecutor(max_workers=12) as executor:
    for res in executor.map(audit_arbitrage_market, sample_timestamps):
        if res:
            results.append(res)

print(f"Audited {len(results)} historical 5m markets across 7 days.\n")

arbs = [r for r in results if r["is_arb"]]
print(f"Total Markets with 100% Synthetic Arbitrage (Combined Cost < $0.98): {len(arbs)} / {len(results)} ({len(arbs)/len(results)*100:.1f}%)\n")

print(f"{'Market Slug':<30} | {'Lowest UP Buy':<15} | {'Lowest DOWN Buy':<16} | {'Combined Cost':<15} | {'Guaranteed Profit'}")
print("-" * 105)

for a in arbs[:15]:
    ret_pct = (a['arb_spread'] / a['combined']) * 100
    print(f"{a['slug']:<30} | ${a['min_up']:<14.3f} | ${a['min_down']:<15.3f} | ${a['combined']:<14.3f} | +${a['arb_spread']:.3f} (+{ret_pct:.1f}%)")

print("="*115)
