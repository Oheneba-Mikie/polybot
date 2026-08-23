import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*80)
print("🔍 AUDITING PREDICT.FUN PRODUCTION 5-MINUTE SERIES (btc-updown-5m):")
print("="*80)

# Check series endpoint
urls_to_test = [
    "https://predict.fun/api/series/btc-updown-5m",
    "https://predict.fun/api/markets?series=btc-updown-5m",
    "https://api.predict.fun/v1/series/btc-updown-5m",
    "https://api-testnet.predict.fun/v1/categories/btc-updown-5m"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

for u in urls_to_test:
    try:
        r = requests.get(u, headers=headers, timeout=5)
        print(f"URL: {u:<55} | Status: {r.status_code} | Body: {r.text[:120]}")
    except Exception as e:
        print(f"URL: {u:<55} | Error: {e}")

print("="*80)
