import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 LIVE TOP-UP VERIFICATION & CANDLE COUNTDOWN")
print("="*95)

try:
    r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=4).json()
    print("🤖 Live Railway Bot Status:")
    print(f"  • Bot Status:    {r.get('status')}")
    print(f"  • Current Phase: {r.get('phase')}")
    print(f"  • Verified Cash: ${r.get('balance'):.2f} USDC")
    print(f"  • Active Candle: {r.get('current_candle')}")
    print(f"  • Live Strike:   ${r.get('strike_price')}")
    print(f"  • Live BTC Price:${r.get('chainlink_price')}")
    print(f"  • Live Gap:      ${r.get('gap') or 0:.2f}")
    print(f"  • Total Trades:  {r.get('total_trades')}")
    print(f"  • Wins:          {r.get('wins')}")
except Exception as e:
    print("State query error:", e)

print("="*95)
