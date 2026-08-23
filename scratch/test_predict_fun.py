import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*80)
print("🔍 TESTING PREDICT.FUN / BINANCE PREDICTION REST API:")
print("="*80)

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

# Test public markets endpoint
try:
    url = "https://api.predict.fun/v1/markets"
    r = requests.get(url, headers=headers, timeout=5)
    print(f"Status Code: {r.status_code}")
    data = r.json()
    print("Response sample:")
    print(json.dumps(data, indent=2)[:500])
except Exception as e:
    print("Error:", e)

# Test docs or open endpoint
try:
    url_testnet = "https://api-testnet.predict.fun/v1/markets"
    r2 = requests.get(url_testnet, headers=headers, timeout=5)
    print(f"\nTestnet Status Code: {r2.status_code}")
    print(json.dumps(r2.json(), indent=2)[:500])
except Exception as e:
    print("Testnet Error:", e)
