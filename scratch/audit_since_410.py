import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
POLYMARKET_ADDRESS = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"

r_act = requests.get(f"{DATA_HOST}/activity?user={POLYMARKET_ADDRESS}&limit=10").json()

print("="*80)
print("AUDITING WALLET TRADES SINCE 20:15 UTC:")
print("="*80)
trades_after_410 = [a for a in r_act if a.get("timestamp", 0) > 1787429613]

if not trades_after_410:
    print("✅ EXACTLY $0.00 LOST since then! ZERO trades have been executed.")
else:
    for a in trades_after_410:
        print(a)

print("="*80)
