import requests
import datetime
import json

# Fetch 1m klines from Binance for 14:05 to 14:20 UTC on Sep 10, 2026
# Let's get timestamp in ms
# Today is 2026-09-10
# 14:10 UTC = 14:10:00
dt_start = datetime.datetime(2026, 9, 10, 14, 5, 0, tzinfo=datetime.timezone.utc)
dt_end = datetime.datetime(2026, 9, 10, 14, 20, 0, tzinfo=datetime.timezone.utc)
start_ms = int(dt_start.timestamp() * 1000)
end_ms = int(dt_end.timestamp() * 1000)

print(f"Querying Binance 1m klines from {dt_start} to {dt_end}...")
url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={start_ms}&endTime={end_ms}"
r = requests.get(url)
if r.status_code == 200:
    klines = r.json()
    print("=== BINANCE 1-MINUTE CANDLES (14:05 - 14:20 UTC) ===")
    for k in klines:
        t = datetime.datetime.fromtimestamp(k[0]/1000, datetime.timezone.utc).strftime('%H:%M:%S')
        o, h, l, c, v = float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])
        print(f"[{t}] Open: ${o:,.2f} | High: ${h:,.2f} | Low: ${l:,.2f} | Close: ${c:,.2f} | Vol: {v:.2f}")

# Also fetch 1s klines or trades if available around 14:10:00 - 14:15:00
dt_window_start = datetime.datetime(2026, 9, 10, 14, 10, 0, tzinfo=datetime.timezone.utc)
dt_window_end = datetime.datetime(2026, 9, 10, 14, 15, 0, tzinfo=datetime.timezone.utc)
w_start_ms = int(dt_window_start.timestamp() * 1000)
w_end_ms = int(dt_window_end.timestamp() * 1000)

url_1s = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1s&startTime={w_start_ms}&endTime={w_start_ms + 60000}"
r_1s = requests.get(url_1s)
if r_1s.status_code == 200:
    klines_1s = r_1s.json()
    print("\n=== FIRST 60 SECONDS OF 14:10 WINDOW (1-SECOND TICKS) ===")
    ptb = float(klines_1s[0][1]) if klines_1s else None
    print(f"Opening PTB at 14:10:00 UTC: ${ptb:,.2f}")
    for k in klines_1s[::5]: # every 5s
        t = datetime.datetime.fromtimestamp(k[0]/1000, datetime.timezone.utc).strftime('%H:%M:%S')
        c = float(k[4])
        diff = c - ptb if ptb else 0
        diff_str = f"+${diff:.2f}" if diff >= 0 else f"-${abs(diff):.2f}"
        print(f"[{t}] BTC: ${c:,.2f} | vs PTB: {diff_str}")
