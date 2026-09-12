import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*115)
print("🔍 COMPREHENSIVE 7-DAY EMPIRICAL AUDIT: SPREAD SCALPING (BUY @ MINUTE 3:30 -> EXIT @ 98¢ OR RESOLUTION)")
print("="*115)

# 1. Fetch 7 full days of 1-minute BTC data (10,080 minutes = 2,016 5-minute windows)
BINANCE_URL = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=1000"

candles_all = []
end_time = int(time.time() * 1000)

print("Downloading 7 full days of 1-minute Bitcoin candlestick data from Binance...")
for batch in range(11): # 11 batches * 1000 = 11,000 1-minute candles (~7.6 days)
    r = requests.get(f"{BINANCE_URL}&endTime={end_time}", timeout=6).json()
    if not r or not isinstance(r, list): break
    candles_all = r + candles_all
    end_time = r[0][0] - 1
    time.sleep(0.1)

# Deduplicate
seen = set()
unique_candles = []
for c in candles_all:
    if c[0] not in seen:
        seen.add(c[0])
        unique_candles.append(c)

unique_candles.sort(key=lambda x: x[0])
total_1m = len(unique_candles)
days = total_1m / 1440.0
print(f"✅ Loaded {total_1m} verified 1-minute candles ({days:.2f} days of continuous market history).\n")

# 2. Build 5-Minute Windows
windows = []
for i in range(0, total_1m - 5, 5):
    chunk = unique_candles[i:i+5]
    if len(chunk) == 5:
        # chunk[0] = Min 0, chunk[1] = Min 1, chunk[2] = Min 2, chunk[3] = Min 3, chunk[4] = Min 4
        open_time_ms = chunk[0][0]
        strike = float(chunk[0][1])          # Open of Minute 0
        min1_close = float(chunk[1][4])      # Close of Minute 1 (T-180s)
        min2_close = float(chunk[2][4])      # Close of Minute 2 (T-120s)
        min3_close = float(chunk[3][4])      # Close of Minute 3 (T-60s)
        min4_high = float(chunk[4][2])       # High of Minute 4
        min4_low = float(chunk[4][3])        # Low of Minute 4
        min4_close = float(chunk[4][4])      # Close of Minute 4 (Resolution)
        
        windows.append({
            "time_ms": open_time_ms,
            "strike": strike,
            "min1_close": min1_close,
            "min2_close": min2_close,
            "min3_close": min3_close,
            "min4_high": min4_high,
            "min4_low": min4_low,
            "min4_close": min4_close,
            "min3_gap": min3_close - strike,
            "final_gap": min4_close - strike
        })

total_windows = len(windows)
print(f"Total 5-minute trading windows evaluated: {total_windows}\n")

# 3. Simulate Strategies across different Min 3:00 Gap Thresholds ($15, $20, $25, $30, $35, $40)
# Rules:
# Entry: Close of Minute 3 (T-60s) if |Gap| >= Threshold
# Realistic Entry Price from Polymarket Order Book Audit:
#   - If Gap $15-$25: Entry @ $0.88
#   - If Gap $25-$35: Entry @ $0.90
#   - If Gap $35+:    Entry @ $0.92
# Exits:
#   Option A: Hold to Resolution ($1.00 if win, $0.00 if lose)
#   Option B: Take Profit @ $0.98 in Minute 4 (if Min 4 continues in favor) OR Bailout if Gap collapses to < $10.00

print("="*115)
print("📊 7-DAY STRATEGY COMPARISON ACROSS ALL 2,000+ 5-MINUTE WINDOWS")
print("="*115)

threshold_tests = [15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 50.0]

for th in threshold_tests:
    eligible = [w for w in windows if abs(w["min3_gap"]) >= th]
    
    # 1. HOLD TO RESOLUTION STATS
    wins_hold = 0
    losses_hold = 0
    pnl_hold = 0.0
    
    # 2. SPREAD SCALPER (TP @ 0.98 / BAILOUT @ GAP < $10)
    tp_wins = 0
    bailouts = 0
    full_losses = 0
    pnl_scalp = 0.0
    
    for w in eligible:
        side = "UP" if w["min3_gap"] > 0 else "DOWN"
        entry_price = 0.88 if th < 25 else (0.90 if th < 35 else 0.92)
        stake = 5.00 # $5.00 flat stake per trade for fair comparison
        shares = stake / entry_price
        
        # Hold to resolution
        if (side == "UP" and w["final_gap"] > 0) or (side == "DOWN" and w["final_gap"] < 0):
            wins_hold += 1
            pnl_hold += shares * (1.00 - entry_price)
        else:
            losses_hold += 1
            pnl_hold -= stake
            
        # Scalper with TP @ 0.98 & Bailout
        # In Minute 4:
        # If UP: did price move further UP (Min 4 High > Min 3 Close)? -> Hits TP @ 0.98
        # If DOWN: did price move further DOWN (Min 4 Low < Min 3 Close)? -> Hits TP @ 0.98
        # If gap collapsed below $10.00 -> Bailout @ 0.86 (-4c scratch)
        
        hit_tp = False
        hit_bailout = False
        
        if side == "UP":
            if (w["min4_high"] - w["strike"]) >= (abs(w["min3_gap"]) + 5.0):
                hit_tp = True
            elif (w["min4_low"] - w["strike"]) < 10.0:
                hit_bailout = True
        else:
            if (w["strike"] - w["min4_low"]) >= (abs(w["min3_gap"]) + 5.0):
                hit_tp = True
            elif (w["strike"] - w["min4_high"]) < 10.0:
                hit_bailout = True
                
        if hit_tp:
            tp_wins += 1
            pnl_scalp += shares * (0.98 - entry_price)
        elif hit_bailout:
            bailouts += 1
            pnl_scalp -= shares * (entry_price - 0.86) # minor 4c scratch
        else:
            # Resolved at close
            if (side == "UP" and w["final_gap"] > 0) or (side == "DOWN" and w["final_gap"] < 0):
                tp_wins += 1
                pnl_scalp += shares * (1.00 - entry_price)
            else:
                full_losses += 1
                pnl_scalp -= stake

    win_rate_hold = (wins_hold / len(eligible) * 100) if eligible else 0.0
    win_rate_scalp = (tp_wins / len(eligible) * 100) if eligible else 0.0
    
    print(f"🔹 Gap Threshold: >= ${th:.1f} (Qualified Trades: {len(eligible)} / {total_windows} windows | {len(eligible)/days:.1f} trades/day)")
    print(f"   [Strategy A: Hold Blindly to 5:00 Close]")
    print(f"      • Win Rate:   {win_rate_hold:.2f}% ({wins_hold} Wins, {losses_hold} Losses)")
    print(f"      • Net PnL:    ${pnl_hold:+,.2f} USDC (on $5 flat stakes)")
    print(f"   [Strategy B: Spread Scalp + Bailout (TP @ 98¢ / Bailout @ Gap < $10)]")
    print(f"      • Win Rate:   {win_rate_scalp:.2f}% ({tp_wins} TP Wins, {bailouts} Bailouts, {full_losses} Full Losses)")
    print(f"      • Net PnL:    ${pnl_scalp:+,.2f} USDC (on $5 flat stakes)")
    print("-" * 115)

print("="*115)
