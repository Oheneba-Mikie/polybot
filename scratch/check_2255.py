import requests, datetime

t_start = int(datetime.datetime(2026, 9, 17, 22, 55, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)
t_end = t_start + 300000

r = requests.get(f'https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={t_start}&endTime={t_end}').json()
o0 = float(r[0][1])
print("22:55 CANDLE MINUTE-BY-MINUTE BREAKDOWN:")
print("Candle Open Strike:", o0)
for k in r:
    t = datetime.datetime.fromtimestamp(k[0]/1000, datetime.timezone.utc).strftime('%H:%M:%S')
    o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
    elapsed_sec = int((k[0] - t_start)/1000)
    delta = c - o0
    peak = h - o0
    low = l - o0
    print(f"T+{elapsed_sec:03d}s ({t}) -> Close: {c} | Move from Open: {delta:+.1f} | Peak: {peak:+.1f} | Low: {low:+.1f}")
