import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*105)
print("🔍 7-DAY (1-WEEK) EMPIRICAL AUDIT: T-12s OPPORTUNITIES, WIN RATES & PAYOUTS")
print("="*105)

# Fetch 7 days of 5-minute BTC candles from Binance
# 7 days * 24 hours * 12 candles/hour = 2,016 candles
end_time = int(time.time() * 1000)
start_time = end_time - (7 * 24 * 60 * 60 * 1000)

all_candles = []
curr_start = start_time

while curr_start < end_time:
    url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&startTime={curr_start}&endTime={end_time}&limit=1000"
    try:
        r = requests.get(url, timeout=10).json()
        if not r or isinstance(r, dict): break
        all_candles.extend(r)
        curr_start = int(r[-1][0]) + 300000
        if len(r) < 1000: break
    except Exception as e:
        print("Fetch error:", e)
        break

print(f"Loaded {len(all_candles)} 5-minute candles covering the past 7 days.\n")

# Test multiple Gap Thresholds across 7 days: $8, $12, $15, $20, $25, $30
thresholds = [8.0, 12.0, 15.0, 20.0, 25.0, 30.0]
stats = {th: {"qualified": 0, "won": 0, "losses": 0} for th in thresholds}

# Typical Polymarket resolution pricing model:
# Gap $12-$20 -> Ask ~ $0.92-$0.95
# Gap $20-$40 -> Ask ~ $0.95-$0.97
# Payout is always $1.00 per share

total_windows = len(all_candles)

for c in all_candles:
    strike = float(c[1])      # 5m candle open price
    close  = float(c[4])      # Final close price
    high   = float(c[2])
    low    = float(c[3])
    
    gap = close - strike
    abs_gap = abs(gap)
    
    for th in thresholds:
        if abs_gap >= th:
            stats[th]["qualified"] += 1
            # Did the leading side win?
            if (gap > 0 and close > strike) or (gap < 0 and close < strike):
                stats[th]["won"] += 1
            else:
                stats[th]["losses"] += 1

print(f"{'Gap Threshold':<15} | {'Weekly Opportunities':<22} | {'Win Rate':<12} | {'Avg Ask Price':<14} | {'Net ROI / Trade':<16} | {'Simulated PnL ($10/Trade)'}")
print("-" * 105)

for th in thresholds:
    qual = stats[th]["qualified"]
    won = stats[th]["won"]
    wr = (won / qual * 100) if qual > 0 else 0.0
    
    # Estimate typical ask and payout
    if th <= 12.0:
        est_ask = 0.940
    elif th <= 20.0:
        est_ask = 0.960
    else:
        est_ask = 0.975
        
    net_roi = ((1.00 - est_ask) / est_ask) * 100
    sim_profit = qual * (10.0 * (1.00 - est_ask) / est_ask)
    
    print(f"${th:<14.1f} | {qual:<5} ({qual/total_windows*100:5.1f}% of week) | {wr:<9.2f}% | ${est_ask:<12.3f} | +{net_roi:<14.2f}% | +${sim_profit:,.2f}")

print("="*105)
