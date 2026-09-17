import requests
import datetime

# Start: 07:20 UTC, End: 07:35 UTC on 2026-09-17
start = "2026-09-17T07:20:00Z"
end   = "2026-09-17T07:35:00Z"

url = f"https://api.exchange.coinbase.com/products/BTC-USD/candles?start={start}&end={end}&granularity=60"
r = requests.get(url, timeout=5).json()

print("Coinbase 1-minute BTC candles (07:20 - 07:35 UTC):")
if isinstance(r, list):
    for k in sorted(r, key=lambda x: x[0]):
        # [time, low, high, open, close, volume]
        t_str = datetime.datetime.fromtimestamp(k[0], datetime.timezone.utc).strftime("%H:%M:%S")
        print(f"  {t_str}: Open={k[3]:.2f} | High={k[2]:.2f} | Low={k[1]:.2f} | Close={k[4]:.2f}")
