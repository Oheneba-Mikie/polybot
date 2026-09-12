import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 ON-CHAIN BALANCE & RECENT TRADES AUDIT")
print("="*95)

addr = "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"

try:
    r_trades = requests.get(f"https://data-api.polymarket.com/trades?user={addr}&limit=10", timeout=5).json()
    print(f"Polymarket Data API Trade Count for {addr}: {len(r_trades)}")
    for t in r_trades:
        dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t.get("timestamp", 0)))
        print(f"  • [{dt}] {t.get('side')} {t.get('size')} sh @ ${t.get('price')} | {t.get('title')}")
except Exception as e:
    print("Trade API Error:", e)

try:
    r_pos = requests.get(f"https://data-api.polymarket.com/positions?user={addr}", timeout=5).json()
    print(f"\nOpen/Unredeemed Positions: {len(r_pos)}")
    for p in r_pos:
        sz = float(p.get("size", 0))
        if sz > 0.001:
            print(f"  • {sz:.3f} sh of {p.get('outcome')} on {p.get('title')} (Value: ${float(p.get('currentValue', 0)):.2f})")
except Exception as e:
    print("Positions API Error:", e)

print("="*95)
