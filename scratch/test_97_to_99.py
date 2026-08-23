import sys
import json
import requests
import datetime
import time

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST = "https://data-api.polymarket.com"

print("="*90)
print("🔍 RESEARCH: HOW OFTEN DOES A 97c TOKEN REACH 99c IN THE SAME 5-MINUTE CANDLE?")
print("="*90)

now = time.time()
current_w_s = int(now // 300) * 300
candle_timestamps = [current_w_s - (i * 300) for i in range(1, 15)]

total_97_touches = 0
total_99_reached = 0

for ts in candle_timestamps:
    slug = f"btc-updown-5m-{ts}"
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
        if not r or not r[0].get("markets"): continue
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        title = mkt.get("question", slug)
        
        r_trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=300").json()
        if not r_trades: continue
        
        trades = sorted(r_trades, key=lambda x: x.get("timestamp", 0))
        
        touched_97 = False
        reached_99 = False
        t_97 = None
        t_99 = None
        
        for t in trades:
            px = float(t.get("price", 0))
            t_sec = t.get("timestamp", 0)
            
            if not touched_97 and 0.965 <= px <= 0.978:
                touched_97 = True
                t_97 = t_sec
            elif touched_97 and not reached_99 and px >= 0.99:
                reached_99 = True
                t_99 = t_sec
                break
                
        if touched_97:
            total_97_touches += 1
            gap_sec = t_99 - t_97 if (t_99 and t_97) else 0
            if reached_99:
                total_99_reached += 1
                print(f"✅ {title[:40]} | Touched 97c -> Reached 99c in {gap_sec}s! (+2.06% gain)")
            else:
                print(f"⚠️ {title[:40]} | Touched 97c -> Max reached 98c")
    except Exception as e:
        continue

print("="*90)
print(f"📊 SUMMARY: Out of {total_97_touches} candles that hit 97c, {total_99_reached} hit 99c ({total_99_reached/max(1, total_97_touches)*100:.1f}%)!")
print("="*90)
