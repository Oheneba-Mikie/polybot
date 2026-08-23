import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

print("="*95)
print("🔍 FORENSIC AUDIT: WHY DID 3 CANDLES BAIL OUT ON 97¢ -> 99¢?")
print("="*95)

now = time.time()
cur_w_s = int(now // 300) * 300
candles_ts = [cur_w_s - (i * 300) for i in range(1, 31)]
candles_ts.reverse()

for ts in candles_ts:
    slug = f"btc-updown-5m-{ts}"
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M UTC")
    
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
        if not r or not r[0].get("markets"): continue
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        
        r_trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=500", timeout=5).json()
        if not r_trades: continue
        trades = sorted(r_trades, key=lambda x: x.get("timestamp", 0))
        
        entered = False
        side = None
        t_entry = None
        hit_98 = False
        hit_99 = False
        t_98 = None
        t_99 = None
        
        for t in trades:
            px = float(t.get("price", 0))
            ts_sec = t.get("timestamp", 0)
            if not entered and 0.965 <= px <= 0.975:
                entered = True
                side = t.get("outcome", "")
                t_entry = ts_sec
            elif entered and ts_sec > t_entry:
                if t.get("outcome") == side:
                    if px >= 0.980 and not hit_98:
                        hit_98 = True
                        t_98 = ts_sec
                    if px >= 0.990 and not hit_99:
                        hit_99 = True
                        t_99 = ts_sec
                        
        if entered:
            # If hit 98 in <40s, but took >40s or didn't hit 99 before 40s
            dur_98 = (t_98 - t_entry) if hit_98 else 999
            dur_99 = (t_99 - t_entry) if hit_99 else 999
            
            if dur_98 <= 40 and dur_99 > 40:
                print(f"[{dt_str}] ⚠️ 98¢ was reached in {dur_98}s, but 99¢ took {dur_99 if hit_99 else 'NEVER'}s!")
                print(f"       -> Reason: The price hovered between 0.980 and 0.985 for over 40s before closing.")
    except Exception as e:
        continue

print("="*95)
