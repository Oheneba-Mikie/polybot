import requests
import json
import datetime

# Query Binance 1s klines or trades for BTCUSDT around 07:25 to 07:30 UTC on 2026-09-17 (today)
# Start time: 07:28:30 UTC
# End time: 07:30:10 UTC

start_ts = int(datetime.datetime(2026, 9, 17, 7, 28, 30, tzinfo=datetime.timezone.utc).timestamp() * 1000)
end_ts   = int(datetime.datetime(2026, 9, 17, 7, 30, 30, tzinfo=datetime.timezone.utc).timestamp() * 1000)

url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1s&startTime={start_ts}&endTime={end_ts}&limit=200"

try:
    r = requests.get(url, timeout=5).json()
    print("Binance BTC Spot around 07:29:00 - 07:30:00 UTC:")
    if isinstance(r, list):
        for k in r[::5]: # every 5 seconds
            ts = datetime.datetime.fromtimestamp(k[0]/1000, datetime.timezone.utc).strftime("%H:%M:%S")
            op, hi, lo, cl = float(k[1]), float(k[2]), float(k[3]), float(k[4])
            print(f"  {ts}: Open={op:.2f} | High={hi:.2f} | Low={lo:.2f} | Close={cl:.2f}")
    else:
        print(r)
except Exception as e:
    print(f"Error: {e}")
