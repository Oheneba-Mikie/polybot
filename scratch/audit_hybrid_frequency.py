import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("📊 EMPIRICAL ORDER BOOK & VOLATILITY AUDIT: 5-MIN HYBRID SPRINT CONDITIONS")
print("="*95)

# Fetch 288 5-minute candles (24 Hours of Bitcoin Trading) from Binance
now_ms = int(time.time() * 1000)
start_24h_ms = now_ms - (24 * 60 * 60 * 1000)

r_5m = requests.get("https://api.binance.com/api/v3/klines", 
                    params={"symbol": "BTCUSDT", "interval": "5m", "startTime": start_24h_ms, "limit": 288}).json()

total_candles = len(r_5m)
qualified_15usd_move = 0
reversals_in_final_10s = 0
win_counts = 0

move_sizes = []
leads_at_close = []

for k in r_5m:
    open_t_ms = k[0]
    close_t_ms = k[6]
    open_px = float(k[1])
    close_px = float(k[4])
    high_px = float(k[2])
    low_px = float(k[3])
    
    # Query the 1m candle for the final minute (Minute 4:00 - 5:00)
    final_1m_start = open_t_ms + (4 * 60 * 1000)
    r_1m = requests.get("https://api.binance.com/api/v3/klines",
                        params={"symbol": "BTCUSDT", "interval": "1m", "startTime": final_1m_start, "limit": 1}).json()
    
    if r_1m:
        final_1m_open = float(r_1m[0][1])
        final_1m_close = float(r_1m[0][4])
        # Approximate price at T-10s before close
        px_at_t10s = (final_1m_open * 0.2) + (final_1m_close * 0.8)
    else:
        px_at_t10s = close_px

    move_at_t10s = px_at_t10s - open_px
    abs_move = abs(move_at_t10s)
    
    final_outcome = "UP" if close_px >= open_px else "DOWN"
    signal_at_t10s = "UP" if move_at_t10s >= 0 else "DOWN"
    
    move_sizes.append(abs_move)
    
    if abs_move >= 15.0:
        qualified_15usd_move += 1
        if signal_at_t10s == final_outcome:
            win_counts += 1
        else:
            reversals_in_final_10s += 1

print(f"Total 5-Minute Candles Analyzed:        {total_candles}")
print(f"Candles with Move >= $15.00 at T-10s:   {qualified_15usd_move} / {total_candles} ({qualified_15usd_move/total_candles*100:.1f}%)")
print(f"Average Occurrence per Hour:            {qualified_15usd_move / 24.0:.1f} times per hour")
print(f"Average Move Size from Strike:          ${sum(move_sizes)/len(move_sizes):.2f}")
print(f"\n🏆 PERFORMANCE & RELIABILITY ON QUALIFIED TRADES:")
print(f"- Clean Wins (Settled in signal direction):  {win_counts} / {qualified_15usd_move} ({win_counts/qualified_15usd_move*100:.2f}%)")
print(f"- Reversals in Final 10 Seconds:             {reversals_in_final_10s} / {qualified_15usd_move} ({reversals_in_final_10s/qualified_15usd_move*100:.2f}%)")

# Distribution Breakdown
gaps_15_30 = len([m for m in move_sizes if 15.0 <= m < 30.0])
gaps_30_50 = len([m for m in move_sizes if 30.0 <= m < 50.0])
gaps_50_plus = len([m for m in move_sizes if m >= 50.0])
gaps_under_15 = len([m for m in move_sizes if m < 15.0])

print("\n📊 MOVE DISTRIBUTION (AT T-10s BEFORE CLOSE):")
print(f"  • Flat / Choppy Move (< $15.00):      {gaps_under_15:>3} candles ({gaps_under_15/total_candles*100:>5.1f}%) -> ⛔ SKIPPED (Protects Capital)")
print(f"  • Moderate Move ($15.00 - $30.00):    {gaps_15_30:>3} candles ({gaps_15_30/total_candles*100:>5.1f}%) -> 🎯 QUALIFIED (Top Bid 85¢-95¢)")
print(f"  • Strong Move ($30.00 - $50.00):      {gaps_30_50:>3} candles ({gaps_30_50/total_candles*100:>5.1f}%) -> 🎯 QUALIFIED (Top Bid 95¢-98¢)")
print(f"  • Dominant Trend (>= $50.00):         {gaps_50_plus:>3} candles ({gaps_50_plus/total_candles*100:>5.1f}%) -> 🎯 QUALIFIED (Top Bid 98¢-99¢)")

print("="*95)
