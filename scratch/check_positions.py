import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
WALLET = "0x89B489569F1B2384ee02E958444aF6091219bfe9"

print("="*80)
print("🔍 WALLET POSITIONS AND P&L:")
print("="*80)

r = requests.get(f"{DATA_HOST}/positions?user={WALLET}", timeout=5).json()
print(f"Total open positions: {len(r)}")
for p in r:
    title = p.get("title", "")
    outcome = p.get("outcome", "")
    size = float(p.get("size", 0))
    cur_val = float(p.get("currentValue", 0))
    avg_price = float(p.get("avgPrice", 0))
    cash = float(p.get("cash", 0))
    redeemable = p.get("redeemable", False)
    print(f"- {title[:40]} | Outcome: {outcome} | Size: {size:.2f} shares | Value: ${cur_val:.2f} | Redeemable: {redeemable}")

print("="*80)
