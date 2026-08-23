import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Search for any 5m category or market
r = requests.get("https://api-testnet.predict.fun/v1/categories?limit=50", timeout=5).json()
cats = r.get("data", [])

print("="*80)
print("🔍 SEARCHING FOR 5M VS 15M MARKETS ON PREDICT.FUN / BINANCE:")
print("="*80)

found_5m = []
found_15m = []

for c in cats:
    slug = c.get("slug", "")
    if "5m" in slug and "15m" not in slug:
        found_5m.append(slug)
    elif "15m" in slug:
        found_15m.append(slug)

print(f"15-Minute Markets Found ({len(found_15m)}):")
for s in found_15m[:5]:
    print("  •", s)

print(f"\n5-Minute Markets Found ({len(found_5m)}):")
for s in found_5m[:5]:
    print("  •", s)

print("="*80)
