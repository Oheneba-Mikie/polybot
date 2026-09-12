import requests
import json
import datetime
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"

# Check the last 3 completed 5-minute candles
now = time.time()
cur_w_s = int(now // 300) * 300

print("="*95)
print("🔍 ON-CHAIN PROOF: TRADES OCCURRING IN THE FINAL 12 SECONDS (T-12s to T-1s)")
print("="*95)

for offset in range(1, 4):
    w_s = cur_w_s - (offset * 300)
    w_e = w_s + 300
    slug = f"btc-updown-5m-{w_s}"
    
    r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
    if r_evt and r_evt[0].get("markets"):
        mkt = r_evt[0]["markets"][0]
        cid = mkt.get("conditionId")
        q = mkt.get("question")
        
        r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=100").json()
        
        late_trades = []
        for t in r_tr:
            t_sec = t.get("timestamp", 0)
            time_left = w_e - t_sec
            if 0 <= time_left <= 15:
                late_trades.append((time_left, t))
                
        print(f"\n📁 Candle: {slug} ({q})")
        print(f"   Total trades in the FINAL 15 SECONDS: {len(late_trades)}")
        for tl, t in sorted(late_trades, key=lambda x: x[0], reverse=True):
            dt = datetime.datetime.fromtimestamp(t.get("timestamp"), datetime.timezone.utc).strftime("%H:%M:%S")
            out = t.get("outcome")
            sz = float(t.get("size"))
            px = float(t.get("price"))
            side = t.get("side")
            print(f"   ⚡ [T-{tl:.0f}s | {dt} UTC] {side:<4} {out:<4} | {sz:>7.2f} shares @ ${px:.4f}")

print("="*95)
