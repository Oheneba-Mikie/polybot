import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 LIVE WALLET BALANCE & BOT REASON AUDIT")
print("="*95)

addr = "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"

# Query Railway bot state
try:
    r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=4).json()
    print("🤖 Live Railway Bot Status:")
    print(f"  • Current Status: {r.get('status')}")
    print(f"  • Current Phase:  {r.get('phase')}")
    print(f"  • Wallet Cash:    ${r.get('balance'):.2f} USDC")
    print(f"  • Current Candle: {r.get('current_candle')}")
    print(f"  • Live Strike:    ${r.get('strike_price')}")
    print(f"  • Live Gap:       ${r.get('gap') or 0:.2f}")
except Exception as e:
    print("Railway state query error:", e)

print("="*95)
