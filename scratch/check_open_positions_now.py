import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

addr = "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"

print("="*95)
print(f"🔍 CURRENT ACTIVE POSITIONS & REDEMPTIONS FOR {addr}:")
print("="*95)

try:
    r = requests.get(f"https://data-api.polymarket.com/positions?user={addr}").json()
    print(f"Open Positions: {len(r)}")
    for p in r:
        sz = float(p.get("size", 0))
        if sz > 0.01:
            print(f"  • {sz:.3f} shares of {p.get('outcome')} on {p.get('title')} (Current Value: ${float(p.get('currentValue', 0)):.2f})")
except Exception as e:
    print("Error:", e)

try:
    r_act = requests.get(f"https://data-api.polymarket.com/activity?user={addr}&limit=5").json()
    print("\nRecent Activity:")
    for a in r_act:
        dt = time.strftime("%H:%M:%S UTC", time.gmtime(a.get("timestamp", 0)))
        print(f"  [{dt}] {a.get('type')} | {a.get('side')} ${float(a.get('usdcSize', a.get('size', 0))):.2f} | {a.get('title')}")
except Exception as e:
    print("Activity error:", e)

print("="*95)
