import requests
import json
import time
import sys
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

print("="*115)
print("🔍 7-DAY EMPIRICAL GAP STABILITY AUDIT: IF GAP >= $20 AT MINUTE 3:30 - 4:20, HOW OFTEN DOES IT WIN?")
print("="*115)

# Fetch historical BTC 1-minute candle data from Binance for the past 7 days (10,080 minutes)
# to test every 5-minute window
BINANCE_URL = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=1000"

candles_all = []
end_time = int(time.time() * 1000)

for _ in range(7): # Pull ~7,000 1m candles (~5 days)
    r = requests.get(f"{BINANCE_URL}&endTime={end_time}").json()
    if not r: break
    candles_all = r + candles_all
    end_time = r[0][0] - 1

# Deduplicate candles by open timestamp
seen = set()
unique_candles = []
for c in candles_all:
    if c[0] not in seen:
        seen.add(c[0])
        unique_candles.append(c)

unique_candles.sort(key=lambda x: x[0])
print(f"Loaded {len(unique_candles)} consecutive 1-minute BTC candles (~{len(unique_candles)/1440:.1f} days).\n")

# Group into 5-minute windows
# Each 5m window has 5 1-minute candles: Minute 0, Minute 1, Minute 2, Minute 3, Minute 4
# Open of Minute 0 = Strike Price
# Close of Minute 4 = Resolution Price

five_min_windows = []
for i in range(0, len(unique_candles) - 5, 5):
    w = unique_candles[i:i+5]
    if len(w) == 5:
        strike = float(w[0][1])      # Open of Min 0
        min3_price = float(w[3][4])  # Close of Min 3 (T-60s)
        min4_open = float(w[4][1])   # Open of Min 4 (T-60s)
        min4_close = float(w[4][4])  # Close of Min 4 (Resolution)
        
        five_min_windows.append({
            "strike": strike,
            "min3_close": min3_price,
            "min4_open": min4_open,
            "resolution": min4_close,
            "min3_gap": min3_price - strike,
            "min4_open_gap": min4_open - strike,
            "final_gap": min4_close - strike
        })

print(f"Total 5-minute windows analyzed: {len(five_min_windows)}\n")

# Test various Gap Thresholds at Minute 3:00 (Close of Min 3 / T-60s)
thresholds = [10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0]

print(f"{'Min 3:00 Gap (T-60s)':<22} | {'Eligible Windows':<18} | {'Winning Windows':<18} | {'Losses (Reversals)':<20} | {'Win Rate'}")
print("-" * 105)

for th in thresholds:
    eligible = [w for w in five_min_windows if abs(w["min3_gap"]) >= th]
    wins = 0
    losses = 0
    for w in eligible:
        predicted_side = "UP" if w["min3_gap"] > 0 else "DOWN"
        actual_side = "UP" if w["final_gap"] > 0 else "DOWN"
        if predicted_side == actual_side:
            wins += 1
        else:
            losses += 1
            
    wr = (wins / len(eligible) * 100) if eligible else 0.0
    print(f">= ${th:<18.1f} | {len(eligible):<18} | {wins:<18} | {losses:<20} | {wr:.2f}%")

print("="*105)
