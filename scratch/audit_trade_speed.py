import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

addr = "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"

print("="*95)
print("🔍 10:45 AM - 10:50 AM ET TRADE SPEED & TIMING AUDIT")
print("="*95)

# 1. Query Data API trades
try:
    r_tr = requests.get(f"https://data-api.polymarket.com/trades?user={addr}&limit=10").json()
    for t in r_tr[:3]:
        dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t.get("timestamp", 0)))
        print(f"  Trade: {dt} | {t.get('side')} {t.get('size')} sh @ ${t.get('price')} (TX: {t.get('transactionHash')[:14]}...) | {t.get('title')}")
except Exception as e:
    print("Trade query error:", e)

# 2. Query Container Logs
print("\n📋 Container Execution Logs for this Trade:")
try:
    r_state = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=6).json()
    for l in r_state.get("logs", []):
        if "14:4" in l or "14:5" in l:
            print(f"  {l}")
except Exception as e:
    print("Log query error:", e)

print("="*95)
