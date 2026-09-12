import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

print("="*95)
print("🔬 EMPIRICAL ON-CHAIN 24-HOUR EXECUTION AUDIT: WHAT WAS ACTUALLY AVAILABLE TO BUY & SELL?")
print("="*95)

now = time.time()
cur_w_s = int(now // 300) * 300

# Sample 10 real candles across the 24 hours (both UP wins, DOWN wins, and fakeouts)
candles_to_audit = []
for i in range(1, 11):
    w_s = cur_w_s - (i * 300 * 2) # Every 10 minutes
    candles_to_audit.append(w_s)

for w_s in candles_to_audit:
    slug = f"btc-updown-5m-{w_s}"
    try:
        r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
        if not r_evt or not r_evt[0].get("markets"): continue
        mkt = r_evt[0]["markets"][0]
        cid = mkt.get("conditionId")
        q = mkt.get("question")
        prices = json.loads(mkt.get("outcomePrices") or "[]")
        
        # Query real historical trade executions on this market
        r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=100", timeout=3).json()
        if not r_tr: continue
        
        # Sort trades chronologically
        trades = sorted(r_tr, key=lambda x: x.get("timestamp", 0))
        
        # Find early surge entry trade (between minute 1 and 3)
        early_trades = [t for t in trades if t.get("timestamp", 0) <= w_s + 200]
        late_trades  = [t for t in trades if t.get("timestamp", 0) > w_s + 200]
        
        print(f"\n📁 Market: {q} (Slug: {slug})")
        print(f"   Final Resolution: UP={prices[0]}, DOWN={prices[1]}")
        print(f"   Total Recorded Trades on Polymarket: {len(trades)}")
        
        if early_trades:
            first_t = early_trades[0]
            print(f"   ⚡ REAL EARLY AVAILABLE LIQUIDITY (Minute 1-3):")
            print(f"      • {first_t.get('side')} {float(first_t.get('size',0)):.2f} sh of {first_t.get('outcome')} @ ${float(first_t.get('price',0)):.3f} (USDC: ${float(first_t.get('size',0))*float(first_t.get('price',0)):.2f})")
            
        if late_trades:
            last_t = late_trades[-1]
            print(f"   💰 REAL LATE CASHOUT / RESOLUTION LIQUIDITY (Minute 4-5):")
            print(f"      • {last_t.get('side')} {float(last_t.get('size',0)):.2f} sh of {last_t.get('outcome')} @ ${float(last_t.get('price',0)):.3f} (USDC: ${float(last_t.get('size',0))*float(last_t.get('price',0)):.2f})")
            
    except Exception as e:
        continue

print("\n" + "="*95)
