import requests
import json
import time

print("Checking live Railway dashboard status...")
time.sleep(5) # Wait for build

try:
    r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=5).json()
    print("Live Bot State:")
    print(f"  Status: {r.get('status')}")
    print(f"  Current Candle: {r.get('current_candle')}")
    print(f"  BTC Strike: {r.get('strike_price')}")
    print(f"  Balance: {r.get('balance_usdc')} USDC")
    print(f"  Phase: {r.get('phase')}")
    print("Recent Logs:")
    for l in r.get("logs", [])[-6:]:
        print(f"   {l}")
except Exception as e:
    print(f"Railway is rebuilding: {e}")
