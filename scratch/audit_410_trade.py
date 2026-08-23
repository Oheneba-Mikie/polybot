import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
POLYMARKET_ADDRESS = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"

r_act = requests.get(f"{DATA_HOST}/activity?user={POLYMARKET_ADDRESS}&limit=10").json()

print("="*80)
print("AUDITING EXACT TRADE DETAILS FOR 4:10PM MARKET:")
print("="*80)

for a in r_act:
    if "4:10PM-4:15PM" in a.get("title", ""):
        print(json.dumps(a, indent=2))
