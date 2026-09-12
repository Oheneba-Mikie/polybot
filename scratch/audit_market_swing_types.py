import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*115)
print("🔍 7-DAY AUDIT: WHAT IF WE PLACE LIMIT BUYS ON BOTH SIDES (e.g. 45¢ UP + 45¢ DOWN)?")
print("="*115)

# Pull 7 days of 1-minute BTC candles (11,000 candles = 2,199 5-minute windows)
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

windows = []
for i in range(0, len(unique_candles) - 5, 5):
    chunk = unique_candles[i:i+5]
    if len(chunk) == 5:
        strike = float(chunk[0][1])
        # Find maximum high and minimum low across the entire 5 minutes
        candle_highs = [float(c[2]) for c in chunk]
        candle_lows = [float(c[3]) for c in chunk]
        max_high = max(candle_highs)
        min_low = min(candle_lows)
        res_price = float(chunk[4][4])
        
        # Max upward excursion & max downward excursion
        up_swing = max_high - strike
        down_swing = strike - min_low
        
        windows.append({
            "strike": strike,
            "up_swing": up_swing,
            "down_swing": down_swing,
            "both_swung_15usd": (up_swing >= 15.0 and down_swing >= 15.0),
            "both_swung_20usd": (up_swing >= 20.0 and down_swing >= 20.0),
            "both_swung_10usd": (up_swing >= 10.0 and down_swing >= 10.0),
            "one_way_trend": (up_swing >= 30.0 and down_swing < 10.0) or (down_swing >= 30.0 and up_swing < 10.0)
        })

total_w = len(windows)
print(f"Total 5-minute windows analyzed: {total_w}\n")

swung_10 = sum(1 for w in windows if w["both_swung_10usd"])
swung_15 = sum(1 for w in windows if w["both_swung_15usd"])
swung_20 = sum(1 for w in windows if w["both_swung_20usd"])
one_way = sum(1 for w in windows if w["one_way_trend"])

print(f"{'Market Behavior (7-Day Replay)':<50} | {'Window Count':<16} | {'Percentage'}")
print("-" * 95)
print(f"{'Two-Way Swing (Both UP & DOWN swung >= $10.00)':<50} | {swung_10:<16} | {swung_10/total_w*100:.2f}%")
print(f"{'Two-Way Swing (Both UP & DOWN swung >= $15.00)':<50} | {swung_15:<16} | {swung_15/total_w*100:.2f}%")
print(f"{'Two-Way Swing (Both UP & DOWN swung >= $20.00)':<50} | {swung_20:<16} | {swung_20/total_w*100:.2f}%")
print(f"{'One-Way Runaway Trend (Clean breakout in 1 direction)':<50} | {one_way:<16} | {one_way/total_w*100:.2f}%")
print("="*115)
