import requests
import json
import time
import datetime
import sys
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

print("="*115)
print("🔍 100% 7-DAY EMPIRICAL AUDIT: TESTING FULL-WEEK AVAILABILITY OF THE 2-LEG ARBITRAGE")
print("="*115)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# 1. Pull 7 days of 1-minute BTC candles (10,080 candles = 2,016 5-minute windows)
BINANCE_URL = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=1000"
candles_all = []
end_time = int(time.time() * 1000)

print("Fetching full 7-day 1-minute BTC candle dataset from Binance...")
for batch in range(11):
    r = requests.get(f"{BINANCE_URL}&endTime={end_time}", timeout=6).json()
    if not r or not isinstance(r, list): break
    candles_all = r + candles_all
    end_time = r[0][0] - 1

seen = set()
unique_candles = []
for c in candles_all:
    if c[0] not in seen:
        seen.add(c[0])
        unique_candles.append(c)

unique_candles.sort(key=lambda x: x[0])
print(f"✅ Loaded {len(unique_candles)} consecutive 1-minute candles ({len(unique_candles)/1440:.1f} days).\n")

# 2. Group into 5-minute windows
total_windows = len(unique_candles) // 5
windows = []
for i in range(0, len(unique_candles) - 5, 5):
    chunk = unique_candles[i:i+5]
    if len(chunk) == 5:
        strike = float(chunk[0][1])          # Open of Min 0
        min3_close = float(chunk[3][4])      # Close of Min 3 (T-60s)
        min4_high = float(chunk[4][2])       # High of Min 4
        min4_low = float(chunk[4][3])        # Low of Min 4
        min4_close = float(chunk[4][4])      # Resolution Price
        
        windows.append({
            "strike": strike,
            "min3_gap": min3_close - strike,
            "min4_high_gap": min4_high - strike,
            "min4_low_gap": min4_low - strike,
            "final_gap": min4_close - strike
        })

print(f"Total 5-minute trading windows evaluated: {len(windows)}\n")

# 3. Audit what happens when Leg 1 is entered at Minute 3:00 (T-60s) when Gap >= $30.00:
# Leg 1: Buy Winner @ ~90c
# Leg 2: Attempt to buy Loser @ 1c - 3c in Minute 4
# Does Leg 2 become available? (Requires Gap in Min 4 to remain >= $30 so Loser price drops to <= 3c)
# What if Gap collapses? (Leg 2 never fills, and Leg 1 is exposed!)

eligible_windows = [w for w in windows if abs(w["min3_gap"]) >= 30.0]

both_legs_filled = 0
reversals_before_leg2 = 0
gap_held_to_close = 0

for w in eligible_windows:
    side = "UP" if w["min3_gap"] > 0 else "DOWN"
    
    # Check if gap continued to expand/hold in Min 4 so Loser dropped to 1c:
    if side == "UP":
        # Gap stayed positive and finished positive
        if w["final_gap"] >= 20.0:
            both_legs_filled += 1
            gap_held_to_close += 1
        elif w["final_gap"] > 0:
            gap_held_to_close += 1 # Won, but Loser might not have hit 1c
        else:
            reversals_before_leg2 += 1 # REVERSAL! Leg 1 lost!
    else:
        if w["final_gap"] <= -20.0:
            both_legs_filled += 1
            gap_held_to_close += 1
        elif w["final_gap"] < 0:
            gap_held_to_close += 1
        else:
            reversals_before_leg2 += 1

print("="*115)
print(f"📊 FULL 7-DAY AUDIT OF 2-LEG ARBITRAGE AT GAP >= $30.00 ({len(eligible_windows)} Qualified Windows):")
print("="*115)
print(f"  • Total Qualified Windows (Gap >= $30 at Min 3:00):  {len(eligible_windows)}")
print(f"  • Windows where Leg 2 (1¢-3¢ Loser) Became Available: {both_legs_filled} ({both_legs_filled/len(eligible_windows)*100:.2f}%)")
print(f"  • Windows where Trend Won at Resolution:            {gap_held_to_close} ({gap_held_to_close/len(eligible_windows)*100:.2f}%)")
print(f"  • Windows with Late Reversals (Leg 1 Exposed):        {reversals_before_leg2} ({reversals_before_leg2/len(eligible_windows)*100:.2f}%)")
print("="*115)
