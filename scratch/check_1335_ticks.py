import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

start_ms = 1787751300 * 1000
r_binance = requests.get("https://api.binance.com/api/v3/klines", 
                         params={"symbol": "BTCUSDT", "interval": "1m", "startTime": start_ms, "limit": 6}).json()

print("📈 13:35 - 13:40 BINANCE TICK BREAKDOWN (Strike was $78,343.53):")
for b in r_binance:
    t_dt = datetime.datetime.fromtimestamp(b[0]/1000, datetime.timezone.utc).strftime("%H:%M UTC")
    o, h, l, c = float(b[1]), float(b[2]), float(b[3]), float(b[4])
    strike = 78343.53
    gap = c - strike
    print(f"   [{t_dt}] Open: ${o:.2f} | Close: ${c:.2f} | Gap vs Strike: ${gap:+.2f}")
