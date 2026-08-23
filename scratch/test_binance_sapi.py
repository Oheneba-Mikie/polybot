import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*80)
print("🔍 TESTING BINANCE NATIVE PREDICTION MARKETS SAPI ENDPOINTS:")
print("="*80)

BINANCE_API = "https://api.binance.com"

# Check sapi/v1 prediction endpoints
test_endpoints = [
    "/sapi/v1/prediction/markets",
    "/sapi/v1/prediction/openMarkets",
    "/sapi/v1/prediction/orderbook",
    "/sapi/v1/prediction/trade"
]

for ep in test_endpoints:
    try:
        r = requests.get(f"{BINANCE_API}{ep}", timeout=4)
        print(f"Endpoint: {ep:<35} | Status: {r.status_code} | Body: {r.text[:120]}")
    except Exception as e:
        print(f"Endpoint: {ep:<35} | Error: {e}")

print("="*80)
