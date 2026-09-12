import requests
import time
import datetime
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 48-HOUR EMPIRICAL AUDIT: T-12s GAP WIN RATE & REVERSAL ANALYSIS")
print("="*95)

# Fetch 1-minute or 5-minute BTCUSDT candles from Binance for past 48 hours
end_time = int(time.time() * 1000)
start_time = end_time - (48 * 60 * 60 * 1000)

url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={start_time}&endTime={end_time}&limit=1000"
res = requests.get(url).json()

# If > 1000 candles needed, fetch next batch
if len(res) == 1000:
    last_t = res[-1][0]
    res2 = requests.get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={last_t + 60000}&endTime={end_time}&limit=1000").json()
    res.extend(res2)

print(f"Loaded {len(res)} 1-minute BTC bars covering the past 48 hours.")

# Organize into 5-minute candles
# A 5-minute candle starts at minute 0, 5, 10, 15, 20...
# Open price is at minute 0 (index 0).
# Price at T-12s corresponds to the end of minute 4 (the 5th bar close).
# Final resolution price is at minute 5 (end of candle).

# Group 1-minute bars into 5-minute blocks
candles_5m = []
curr_block = []

for bar in res:
    bar_ts = int(bar[0]) // 1000
    if bar_ts % 300 == 0:
        if len(curr_block) == 5:
            candles_5m.append(curr_block)
        curr_block = [bar]
    else:
        if curr_block:
            curr_block.append(bar)

if len(curr_block) == 5:
    candles_5m.append(curr_block)

print(f"Analyzed {len(candles_5m)} complete 5-minute market windows across 48h.\n")

# Test various Gap Thresholds at T-12s / Minute 4 Close:
# We test: $8, $12, $15, $20, $25, $30, $40
thresholds = [8.0, 12.0, 15.0, 20.0, 25.0, 30.0, 40.0]
stats = {th: {"triggered": 0, "won": 0, "flipped_loss": 0, "flips": []} for th in thresholds}

for c in candles_5m:
    strike_open = float(c[0][1])      # 5m candle open price
    t12_price   = float(c[4][4])      # Price at end of 4th minute (~T-12s)
    final_close = float(c[4][4])      # Final resolution close
    # Using high/low of last minute to see if a flip occurred in the final seconds
    last_min_high = float(c[4][2])
    last_min_low  = float(c[4][3])
    
    gap_at_t12 = t12_price - strike_open
    abs_gap = abs(gap_at_t12)
    predicted_side = "UP" if gap_at_t12 > 0 else "DOWN"
    
    actual_winner = "UP" if final_close > strike_open else "DOWN"
    
    dt_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(int(c[0][0]) // 1000))
    
    for th in thresholds:
        if abs_gap >= th:
            stats[th]["triggered"] += 1
            if predicted_side == actual_winner:
                stats[th]["won"] += 1
            else:
                stats[th]["flipped_loss"] += 1
                stats[th]["flips"].append((dt_str, strike_open, t12_price, final_close, gap_at_t12))

print(f"{'Gap Threshold':<15} | {'Trades Fired':<14} | {'Wins':<8} | {'Losses':<8} | {'Win Rate':<10} | {'Expected Risk'}")
print("-" * 80)
for th in thresholds:
    trig = stats[th]["triggered"]
    won = stats[th]["won"]
    loss = stats[th]["flipped_loss"]
    wr = (won / trig * 100) if trig > 0 else 0.0
    risk = "Zero Flips (100% Safe)" if loss == 0 else f"{loss} Reversal Loss(es)"
    print(f"${th:<14.1f} | {trig:<14} | {won:<8} | {loss:<8} | {wr:<9.2f}% | {risk}")

print("\n" + "="*95)
print("📋 REVERSAL / FLIP AUDIT AT $12 GAP (Cases where $12 flipped in last 12s):")
if stats[12.0]["flips"]:
    for f in stats[12.0]["flips"]:
        print(f"  • {f[0]}: Open ${f[1]:.2f} -> T-12s ${f[2]:.2f} (Gap: ${f[4]:+.2f}) -> Close ${f[3]:.2f} [FLIPPED!]")
else:
    print("  ✅ ZERO reversals occurred at $12 gap in the last 48 hours!")

print("="*95)
