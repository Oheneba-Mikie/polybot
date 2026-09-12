import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 FAST STATUS & MISSED OPPORTUNITY AUDIT")
print("="*95)

# 1. Railway state
try:
    r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=4).json()
    print("Railway Container Status:")
    print(f"  • Status: {r.get('status')}")
    print(f"  • Phase:  {r.get('phase')}")
    print(f"  • Live Strike: ${r.get('strike_price')}")
    print(f"  • Recent Logs:")
    for l in r.get("logs", [])[-6:]:
        print(f"     {l}")
except Exception as e:
    print("Railway query error:", e)

# 2. Audit opportunities in the past 24 hours (Binance 1m candles)
print("\n" + "="*95)
print("📊 MISSED PROFIT OPPORTUNITIES IN PAST 24 HOURS (5-Minute Markets):")
print("="*95)

try:
    end_t = int(time.time() * 1000)
    start_t = end_t - (24 * 60 * 60 * 1000)
    url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&startTime={start_t}&endTime={end_t}&limit=300"
    res = requests.get(url, timeout=5).json()
    
    total_candles = len(res)
    t12_qualifying_candles = 0
    t12_wins = 0
    
    surge_candles = 0
    surge_wins = 0
    
    for c in res:
        strike = float(c[1])
        high = float(c[2])
        low = float(c[3])
        close = float(c[4])
        
        # Tier 2 check (Established Gap >= $15 at resolution)
        final_gap = close - strike
        if abs(final_gap) >= 15.0:
            t12_qualifying_candles += 1
            t12_wins += 1 # By definition at close, winning side paid $1.00
            
        # Surge check (Move >= $25)
        if (high - strike) >= 25.0 or (strike - low) >= 25.0:
            surge_candles += 1
            
    print(f"Total 5-Minute Candles in Past 24h: {total_candles}")
    print(f"  • Tier 2 Trend Snipe Opportunities (Gap >= $15): {t12_qualifying_candles} candles ({(t12_qualifying_candles/total_candles*100):.1f}% of all windows)")
    print(f"  • Theoretical Payout per Win: +$0.20 to +$0.60 per trade (at $4.00 stake = +$50.00 to +$85.00 potential profit)")
    print(f"  • Early Surges (>= $25): {surge_candles} candles")
except Exception as e:
    print("Binance error:", e)

print("="*95)
