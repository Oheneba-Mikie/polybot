import requests
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

now = time.time()
w_s = int(now // 300) * 300

print(f"Current Time: {datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S UTC')}")
print(f"Candle w_s:   {w_s} ({datetime.datetime.fromtimestamp(w_s, datetime.timezone.utc).strftime('%H:%M:%S UTC')})")

url = "https://api.binance.com/api/v3/klines"
params = {"symbol": "BTCUSDT", "interval": "5m", "startTime": int(w_s * 1000), "limit": 1}
print(f"Query URL: {url} with params: {params}")

r = requests.get(url, params=params).json()
print("Raw Binance Response:", r)
if r and isinstance(r, list) and len(r) > 0:
    open_px = float(r[0][1])
    print(f"✅ Resolved Strike Open Price: ${open_px:.2f}")
else:
    print("❌ Failed to resolve strike price")
