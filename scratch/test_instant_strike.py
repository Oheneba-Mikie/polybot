import requests
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

now = time.time()
w_s = int(now // 300) * 300

r = requests.get("https://api.binance.com/api/v3/klines", params={"symbol": "BTCUSDT", "interval": "5m", "startTime": w_s * 1000, "limit": 1}, timeout=2).json()
if r:
    open_px = float(r[0][1])
    dt = datetime.datetime.fromtimestamp(w_s, datetime.timezone.utc).strftime("%H:%M:%S")
    print(f"[{dt} UTC] Exact 5m Candle Strike Open Price: ${open_px:.2f}")
