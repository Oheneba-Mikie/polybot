import json
import datetime

with open('scratch/daily_breakdown.json') as f:
    daily = json.load(f)

aug20 = daily['2026-08-20']

print("="*100)
print(f"{'#':<3} | {'UTC Time':<20} | {'T-minus (s)':<12} | {'Side':<5} | {'Price':<6} | {'Shares':<12} | {'Cost ($)':<9} | {'Market Title'}")
print("="*100)

for idx, t in enumerate(aug20['details'], 1):
    for b in t['buys']:
        ts = b['ts']
        dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        # 5m window boundary
        w_start = (ts // 300) * 300
        w_end = w_start + 300
        t_minus = w_end - ts
        print(f"{idx:<3} | {dt_str:<20} | T-{t_minus:<10} | {b['outcome']:<5} | {b['price']:<6.3f} | {b['shares']:<12.2f} | ${b['size']:<8.2f} | {t['title'][:40]}")
