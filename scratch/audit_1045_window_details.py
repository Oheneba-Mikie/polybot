import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 COMPREHENSIVE MINUTE-BY-MINUTE AUDIT: 10:45 AM - 10:50 AM ET (14:45 - 14:50 UTC)")
print("="*95)

# 14:45:00 UTC timestamp = 1787841900
# Fetch Binance 1m klines around 14:45 - 14:52 UTC
t_start = (1787841900 - 60) * 1000
t_end = (1787841900 + 420) * 1000

url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={t_start}&endTime={t_end}"
res = requests.get(url).json()

print("📊 Bitcoin Price Movement Across the 5-Minute Candle:")
strike_price = None
for idx, bar in enumerate(res):
    bar_time = time.strftime("%H:%M:%S UTC", time.gmtime(int(bar[0]) / 1000))
    o = float(bar[1])
    h = float(bar[2])
    l = float(bar[3])
    c = float(bar[4])
    if idx == 1: # 14:45:00 UTC bar
        strike_price = o
        print(f"  ⭐ [14:45:00 UTC] 🏁 CANDLE START | Strike Price: ${strike_price:.2f}")
    if strike_price:
        gap = c - strike_price
        print(f"     [{bar_time}] Open: ${o:.2f} | High: ${h:.2f} | Low: ${l:.2f} | Close: ${c:.2f} | Gap: ${gap:+.2f}")

print("\n" + "="*95)
