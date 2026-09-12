import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 LIVE BOT EXECUTION MONITOR")
print("="*95)

try:
    r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=4).json()
    print(f"Status: {r.get('status')}")
    print(f"Phase:  {r.get('phase')}")
    print(f"Balance: ${r.get('balance'):.2f}")
    print(f"Candle: {r.get('current_candle')}")
    print(f"Gap:    ${r.get('gap') or 0:.2f}")
    print(f"Trades: {r.get('total_trades')}")
    print(f"Streak: {r.get('streak')} W")
    print(f"Last Trade: {r.get('last_trade')}")
    print("\nRecent Logs:")
    for l in r.get("logs", [])[-6:]:
        print(f"  {l}")
except Exception as e:
    print("State error:", e)

print("="*95)
