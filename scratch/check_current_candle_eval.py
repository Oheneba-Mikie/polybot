import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 LIVE REAL-TIME EVALUATION LOGS FOR CURRENT CANDLE (22:10-22:15 UTC)")
print("="*95)

try:
    r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=4).json()
    print(f"Bot Status:  {r.get('status')}")
    print(f"Phase:       {r.get('phase')}")
    print(f"Balance:     ${r.get('balance'):.2f}")
    print(f"Candle:      {r.get('current_candle')}")
    print(f"Live Strike: ${r.get('strike_price')}")
    print(f"Live BTC:    ${r.get('chainlink_price')}")
    print(f"Live Gap:    ${r.get('gap') or 0:.2f}")
    print("\n📜 Real-Time Logs:")
    for l in r.get("logs", [])[-10:]:
        print(f"  {l}")
except Exception as e:
    print("State query error:", e)

print("="*95)
