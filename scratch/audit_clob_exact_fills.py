import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*105)
print("🔍 AUDITING ACTUAL HISTORICAL POLYMARKET CLOB TRADES AT T-12s")
print("="*105)

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# Generate 5m candle timestamps for today
now_ts = int(time.time() // 300) * 300
timestamps = [now_ts - (i * 300) for i in range(1, 15)]

audited = 0
found_trades = 0

for ts in timestamps:
    slug = f"btc-updown-5m-{ts}"
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
        if not r or not r[0].get("markets"): continue
        
        mkt = r[0]["markets"][0]
        title = mkt.get("question")
        clob_ids = json.loads(mkt.get("clobTokenIds") or "[]")
        if not clob_ids: continue
        
        audited += 1
        w_e = ts + 300
        
        for tid in clob_ids:
            t_res = requests.get(f"{CLOB_HOST}/trades", params={"market": tid, "limit": 100}, timeout=3).json()
            trades = t_res.get("data", [])
            
            t12_fills = []
            for t in trades:
                trade_ts = float(t.get("timestamp", 0))
                time_left = w_e - trade_ts
                if 0 <= time_left <= 20: # Final 20 seconds of candle
                    t12_fills.append(t)
                    
            if t12_fills:
                found_trades += len(t12_fills)
                total_sz = sum(float(x["size"]) for x in t12_fills)
                prices = [float(x["price"]) for x in t12_fills]
                print(f"🎯 Market: {title}")
                print(f"   • Outcome Token: {tid[:12]}...")
                print(f"   • Real Fills at T-20s down to T-0s: {len(t12_fills)} fills")
                print(f"   • Total Shares Traded: {total_sz:.1f} shares (${sum(float(x['price'])*float(x['size']) for x in t12_fills):.2f} USDC)")
                print(f"   • Fill Price Range: ${min(prices):.3f} to ${max(prices):.3f}")
                print("-" * 80)
    except Exception as e:
        pass

print("\n" + "="*105)
print(f"Total 5m Markets Audited: {audited} | Real Trades Captured in Final Seconds: {found_trades}")
print("="*105)
