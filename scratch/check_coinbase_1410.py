import requests, datetime

dt_window_start = datetime.datetime(2026, 9, 10, 14, 10, 0, tzinfo=datetime.timezone.utc)
start_iso = "2026-09-10T14:05:00Z"
end_iso = "2026-09-10T14:20:00Z"

# Coinbase candles
url = f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60&start={start_iso}&end={end_iso}"
headers = {"User-Agent": "Mozilla/5.0"}
r = requests.get(url, headers=headers, timeout=10)
if r.status_code == 200:
    candles = r.json()
    candles.sort(key=lambda x: x[0])
    print("=== COINBASE 1-MINUTE BTC CANDLES (14:05 - 14:20 UTC) ===")
    for c in candles:
        t = datetime.datetime.fromtimestamp(c[0], datetime.timezone.utc).strftime('%H:%M:%S')
        # [time, low, high, open, close, volume]
        low, high, open_p, close_p, vol = c[1], c[2], c[3], c[4], c[5]
        print(f"[{t}] Open: ${open_p:,.2f} | High: ${high:,.2f} | Low: ${low:,.2f} | Close: ${close_p:,.2f} | Net: ${close_p - open_p:+.2f}")
else:
    print(f"Coinbase status {r.status_code}: {r.text}")
