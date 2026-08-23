import requests
import json
from dotenv import load_dotenv
import os

load_dotenv("scalper_bailout_deploy/.env")

DATA_HOST = "https://data-api.polymarket.com"
POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS", "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8")

r_pos = requests.get(f"{DATA_HOST}/positions?user={POLYMARKET_ADDRESS}&sizeThreshold=0.01").json()
r_act = requests.get(f"{DATA_HOST}/activity?user={POLYMARKET_ADDRESS}&limit=5").json()

print("="*80)
print("WALLET CURRENT STATUS:")
print("="*80)
print("Latest 3 transactions:")
for a in r_act[:3]:
    print(f"  • {a.get('type')} | {a.get('side')} | Price: ${float(a.get('price') or 0):.2f} | Size: {a.get('size')} | Title: {a.get('title')}")

print("\nCurrent Open Positions:")
for p in r_pos:
    if float(p.get('size', 0)) > 0.1:
        print(f"  • {p.get('title')} | {p.get('outcome')} | Size: {p.get('size')} | Val: ${float(p.get('currentValue', 0)):.2f}")
