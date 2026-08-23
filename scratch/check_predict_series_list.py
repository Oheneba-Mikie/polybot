import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*80)
print("🔍 QUERYING PREDICT.FUN /series ENDPOINT:")
print("="*80)

try:
    r = requests.get("https://api-testnet.predict.fun/v1/series", timeout=5).json()
    series_list = r.get("data", [])
    print(f"Fetched {len(series_list)} configured series:")
    for s in series_list:
        print(f"  • Title: {s.get('title')} | Slug: {s.get('slug')} | Recurrence: {s.get('recurrence')}")
except Exception as e:
    print("Error:", e)

print("="*80)
