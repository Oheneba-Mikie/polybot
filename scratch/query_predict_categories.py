import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*80)
print("🔍 QUERYING PREDICT.FUN CATEGORIES & MARKETS:")
print("="*80)

# Test categories endpoint on testnet
try:
    r = requests.get("https://api-testnet.predict.fun/v1/categories", timeout=5).json()
    cats = r.get("data", [])
    print(f"Fetched {len(cats)} categories from Predict.fun.")
    for c in cats:
        print(f"  • Category: {c.get('name')} | Slug: {c.get('slug')}")
except Exception as e:
    print("Categories error:", e)

# Query markets for BTC
try:
    r_m = requests.get("https://api-testnet.predict.fun/v1/markets", timeout=5).json()
    markets = r_m.get("data", [])
    print(f"\nFetched {len(markets)} markets:")
    for m in markets:
        if "btc" in m.get("categorySlug", "").lower() or "bitcoin" in m.get("description", "").lower():
            print(f"  • [BTC Market] ID: {m.get('id')} | Slug: {m.get('categorySlug')} | Precision: {m.get('decimalPrecision')}")
except Exception as e:
    print("Markets error:", e)

print("="*80)
