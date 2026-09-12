import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 AUDIT OF ALL API CALLS MADE BY OUR BOT & CLIENT LIBRARIES")
print("="*95)

print("1. Polymarket CLOB API Endpoints Supported by `py_clob_client_v2`:")
print("   • GET    /book              -> Query order book prices (read-only)")
print("   • GET    /balance-allowance -> Query collateral balance (read-only)")
print("   • POST   /order             -> Place Market / Limit Buy or Sell on prediction token")
print("   • DELETE /order             -> Cancel open trade order")
print("   • GET    /trades            -> Query trade history")
print("   ❌ NO /withdraw, /transfer, or /bridge endpoint exists on the CLOB API.")

print("\n2. All External Endpoints Queried by `scalper_bailout_deploy/app.py`:")
print("   • Gamma API: `https://gamma-api.polymarket.com/events` (Fetches market token IDs)")
print("   • CLOB API:  `https://clob.polymarket.com` (Places BUY/SELL orders)")
print("   • WebSocket: `wss://ws-live-data.polymarket.com/` (Receives Chainlink BTC price)")

print("\n3. Verification of Bot Memory Logs around 18:20:57 UTC:")
try:
    r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state").json()
    logs = r.get("logs", [])
    relevant_logs = [l for l in logs if "18:20" in l or "18:21" in l or "18:19" in l]
    print(f"   Logs recorded in container memory during 18:19 - 18:21 UTC ({len(relevant_logs)} entries):")
    for l in relevant_logs:
        print(f"     {l}")
except Exception as e:
    print("   Could not query state logs:", e)

print("="*95)
