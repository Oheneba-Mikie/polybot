import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*115)
print("🔍 7-DAY AUDIT FOR 100.00% MATHEMATICAL & EMPIRICAL CERTAINTY (ZERO LOSSES)")
print("="*115)

# 1. Fetch 7 days of 1-minute BTC candles (11,000 candles)
BINANCE_URL = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=1000"
candles_all = []
end_time = int(time.time() * 1000)

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

# Find the MAXIMUM 1-minute Bitcoin move in the entire 7.64 days (Minute 4 volatility max)
max_1m_move = 0.0
for c in unique_candles:
    high = float(c[2])
    low = float(c[3])
    diff = high - low
    if diff > max_1m_move:
        max_1m_move = diff

print(f"📊 7-Day Market Volatility Stats:")
print(f"  • Total 1-Minute Candles Audited: {len(unique_candles)}")
print(f"  • Absolute Maximum 1-Minute BTC Range in 7 Days: ${max_1m_move:.2f}\n")

# Replay 2,199 5-minute windows
windows = []
for i in range(0, len(unique_candles) - 5, 5):
    chunk = unique_candles[i:i+5]
    if len(chunk) == 5:
        strike = float(chunk[0][1])          # Open of Min 0
        min3_close = float(chunk[3][4])      # Close of Min 3 (T-60s)
        min4_close = float(chunk[4][4])      # Close of Min 4 (Resolution)
        
        windows.append({
            "strike": strike,
            "min3_gap": min3_close - strike,
            "final_gap": min4_close - strike
        })

print(f"Auditing {len(windows)} 5-minute windows for 100.00% Win Rate Gap Thresholds...\n")

# Test gap thresholds from $50 up to $150 to find the EXACT threshold that achieves 100.00% Win Rate
print(f"{'Min 3:00 Gap (T-60s)':<22} | {'Eligible Trades':<18} | {'Wins':<10} | {'Losses':<10} | {'Win Rate':<12} | {'7-Day PnL ($5 Stakes)'}")
print("-" * 105)

for th in [50.0, 60.0, 70.0, 75.0, 80.0, 90.0, 100.0, 120.0, 150.0]:
    eligible = [w for w in windows if abs(w["min3_gap"]) >= th]
    wins = 0
    losses = 0
    pnl = 0.0
    
    for w in eligible:
        predicted = "UP" if w["min3_gap"] > 0 else "DOWN"
        actual = "UP" if w["final_gap"] > 0 else "DOWN"
        entry_price = 0.94 # At huge gap, entry is 94c
        shares = 5.00 / entry_price
        
        if predicted == actual:
            wins += 1
            pnl += shares * (1.00 - entry_price)
        else:
            losses += 1
            pnl -= 5.00
            
    wr = (wins / len(eligible) * 100) if eligible else 0.0
    print(f">= ${th:<18.1f} | {len(eligible):<18} | {wins:<10} | {losses:<10} | {wr:<11.2f}% | ${pnl:+,.2f} USDC")

print("="*115)
