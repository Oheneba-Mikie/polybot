import requests
import json

proxy_address = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
r_pos = requests.get(f"https://data-api.polymarket.com/positions?user={proxy_address}").json()

print("="*80)
print("AUDITING REDEEMABLE / UNCLAIMED POSITIONS ON POLYMARKET:")
print("="*80)

total_redeemable = 0
for p in r_pos:
    if p.get("redeemable"):
        print(f"Market: {p.get('title')}")
        print(f"  Side: {p.get('outcome')} | Shares: {p.get('size')} | CurPrice: {p.get('curPrice')} | CashPnL: {p.get('cashPnl')}")
        if p.get("curPrice", 0) > 0 or p.get("cashPnl", 0) > 0:
            total_redeemable += p.get("size", 0)

print(f"\nTotal Winning Redeemable Value: ${total_redeemable:.4f}")
print("="*80)
