import requests
import json
import datetime
import time
import sys
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

now = int(time.time())
monday_start = int(datetime.datetime(2026, 8, 24, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp())
timestamps = list(range(monday_start, now - 300, 300))

def get_timing(ts):
    slug = f"btc-updown-5m-{ts}"
    candle_end = ts + 300
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
        if not r or not r[0].get("markets"): return None
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        r_trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=100", timeout=3).json()
        
        # Find earliest trade >= 0.98
        earliest_98_sec_left = None
        for t in reversed(r_trades): # chronological
            px = float(t.get("price", 0))
            if px >= 0.98:
                t_trade = t.get("timestamp", 0)
                sec_left = candle_end - t_trade
                earliest_98_sec_left = sec_left
                break
                
        return earliest_98_sec_left
    except:
        return None

with ThreadPoolExecutor(max_workers=20) as executor:
    timings = list(executor.map(get_timing, timestamps))

valid_timings = [t for t in timings if t is not None and 0 <= t <= 300]
avg_sec_left = sum(valid_timings) / max(1, len(valid_timings))

print(f"Timing Analysis of 98¢/99¢ Occurrences:")
print(f"- Total valid samples: {len(valid_timings)}")
print(f"- Average time before candle close when 98¢ first appears: {avg_sec_left:.1f} seconds")
print(f"- Min time left: {min(valid_timings) if valid_timings else 0}s | Max time left: {max(valid_timings) if valid_timings else 0}s")
