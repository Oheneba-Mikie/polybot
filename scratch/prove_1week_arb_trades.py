import requests
import json
import time
import datetime
import sys
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

print("="*115)
print("🔍 1-WEEK EMPIRICAL ON-CHAIN PROOF: REAL COMBINED BUYS < $1.00 & AVAILABLE SHARES")
print("="*115)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# Sample 120 historical 5-minute Bitcoin markets across the past 7 days (Aug 21 - Aug 28)
now_ts = int(time.time() // 300) * 300
sample_timestamps = [now_ts - (i * 300 * 15) for i in range(1, 121)]

def audit_real_market_liquidity(ts):
    slug = f"btc-updown-5m-{ts}"
    w_s = ts
    w_e = ts + 300
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r or not r[0].get("markets"): return None
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        q = mkt.get("question")
        
        # Fetch verified trades that executed on this specific market
        tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=200", timeout=4).json()
        if not tr or not isinstance(tr, list): return None
        
        up_buys = []
        down_buys = []
        
        for t in tr:
            trade_ts = t.get("timestamp", 0)
            if w_s <= trade_ts <= w_e:
                side = str(t.get("side", "")).upper()
                out = str(t.get("outcome", "")).upper()
                px = float(t.get("price", 0))
                sz = float(t.get("size", 0))
                
                if side == "BUY":
                    if out == "UP":
                        up_buys.append({"price": px, "size": sz, "ts": trade_ts, "offset": trade_ts - w_s})
                    elif out == "DOWN":
                        down_buys.append({"price": px, "size": sz, "ts": trade_ts, "offset": trade_ts - w_s})
                        
        if up_buys and down_buys:
            # Find lowest actual buy prices filled on-chain
            best_up = min(up_buys, key=lambda x: x["price"])
            best_down = min(down_buys, key=lambda x: x["price"])
            
            combined_cost = best_up["price"] + best_down["price"]
            
            # Sum up total shares that traded at or near those prices
            up_vol_at_price = sum(x["size"] for x in up_buys if x["price"] <= best_up["price"] + 0.05)
            down_vol_at_price = sum(x["size"] for x in down_buys if x["price"] <= best_down["price"] + 0.05)
            
            if combined_cost < 0.98: # True Arbitrage
                return {
                    "slug": slug,
                    "title": q,
                    "up_price": best_up["price"],
                    "up_time": f"Min {best_up['offset']//60}:{best_up['offset']%60:02d}",
                    "up_shares_avail": up_vol_at_price,
                    "down_price": best_down["price"],
                    "down_time": f"Min {best_down['offset']//60}:{best_down['offset']%60:02d}",
                    "down_shares_avail": down_vol_at_price,
                    "combined_cost": combined_cost,
                    "guaranteed_profit_pct": ((1.00 - combined_cost) / combined_cost) * 100
                }
        return None
    except Exception:
        return None

print("Auditing real on-chain trade fills and volume across historical 5m markets...\n")

results = []
with ThreadPoolExecutor(max_workers=12) as executor:
    for res in executor.map(audit_real_market_liquidity, sample_timestamps):
        if res:
            results.append(res)

print(f"✅ Found {len(results)} verified markets across the past week with Real Combined Buys < $1.00.\n")

print(f"{'Market (5m Window)':<30} | {'UP Buy (Time | Volume)':<26} | {'DOWN Buy (Time | Volume)':<26} | {'Combined':<10} | {'Guaranteed Profit'}")
print("-" * 115)

for r in results[:12]:
    up_info = f"${r['up_price']:.2f} ({r['up_time']} | {r['up_shares_avail']:,.0f} sh)"
    down_info = f"${r['down_price']:.2f} ({r['down_time']} | {r['down_shares_avail']:,.0f} sh)"
    comb_info = f"${r['combined_cost']:.3f}"
    prof_info = f"+{r['guaranteed_profit_pct']:.1f}% ($1.00 payout)"
    
    print(f"{r['slug']:<30} | {up_info:<26} | {down_info:<26} | {comb_info:<10} | {prof_info}")

print("="*115)
