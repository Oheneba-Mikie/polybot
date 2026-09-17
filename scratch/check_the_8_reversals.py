import requests
import json
import time
import datetime

now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - (i * 300) for i in range(1, 289)]
start_ts = windows[-1] * 1000
end_ts = (windows[0] + 300) * 1000

b1 = requests.get(f'https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={start_ts}&limit=1000').json()
b2 = requests.get(f'https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={b1[-1][0]+60000}&limit=1000').json()
kl = {int(k[0]//1000): {'open': float(k[1]), 'high': float(k[2]), 'low': float(k[3]), 'close': float(k[4])} for k in (b1 + b2)}

reversals = []
for w in windows:
    bars = [kl.get(w + i*60) for i in range(5) if (w + i*60) in kl]
    if len(bars) < 5:
        continue
    o = bars[0]['open']
    c = bars[-1]['close']
    hi = max(b['high'] for b in bars)
    lo = min(b['low'] for b in bars)
    up_m = hi - o
    dn_m = o - lo
    max_m = max(up_m, dn_m)
    if max_m >= 60.0:
        wave_dir = 'UP' if up_m >= dn_m else 'DOWN'
        final_dir = 'UP' if c > o else 'DOWN'
        if wave_dir != final_dir:
            peak_sec = 0
            for i, b in enumerate(bars):
                if wave_dir == 'UP' and b['high'] == hi:
                    peak_sec = i * 60 + 30
                elif wave_dir == 'DOWN' and b['low'] == lo:
                    peak_sec = i * 60 + 30
            reversals.append({
                'w': w,
                'time_utc': datetime.datetime.fromtimestamp(w, datetime.timezone.utc).strftime('%H:%M'),
                'open': o,
                'close': c,
                'max_m': max_m,
                'wave_dir': wave_dir,
                'final_dir': final_dir,
                'peak_sec': peak_sec,
                'bars': bars
            })

print(f"Total Reversals: {len(reversals)}")
for idx, r in enumerate(reversals, 1):
    print(f"#{idx}: Time: {r['time_utc']} UTC | Wave: {r['wave_dir']} (${r['max_m']:.2f}) | Peak approx T+{r['peak_sec']}s (Minute {(r['peak_sec']//60)+1}) | Open: ${r['open']:.2f} -> Close: ${r['close']:.2f} (Winner: {r['final_dir']})")
