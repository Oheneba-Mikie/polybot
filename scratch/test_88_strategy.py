import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

print("="*90)
print("🔍 TESTING 88¢ ENTRY STRATEGY (ALLOWS TRADING WITH $4.43 BALANCE):")
print("="*90)

now = time.time()
cur_w_s = int(now // 300) * 300
candles_ts = [cur_w_s - (i * 300) for i in range(1, 31)]
candles_ts.reverse()

triggers_88 = 0
wins_88 = 0
bailouts_88 = 0

for ts in candles_ts:
    slug = f"btc-updown-5m-{ts}"
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
        
        for t in trades:
            px = float(t.get("price", 0))
            ts_sec = t.get("timestamp", 0)
            if not entered and 0.85 <= px <= 0.88:
                entered = True
                side = t.get("outcome", "")
                t_entry = ts_sec
            elif entered and ts_sec > t_entry:
                if t.get("outcome") == side and px >= 0.93:
                    wins_88 += 1
                    break
                elif (ts_sec - t_entry) > 40.0 or (t.get("outcome") == side and px < 0.80):
                    bailouts_88 += 1
                    break
        if entered:
            triggers_88 += 1
    except Exception:
        continue

print(f"Total 88¢ Triggers: {triggers_88}")
print(f"Wins (88¢ -> 93¢):  {wins_88} ({wins_88/max(1, triggers_88)*100:.1f}%)")
print(f"Bailouts:           {bailouts_88}")
print("="*90)
