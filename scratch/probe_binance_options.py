import requests
import json

print("="*80)
print("EXPLORING BINANCE PREDICTION & OPTIONS CONTRACTS")
print("="*80)

# Check Binance Options exchange info (eapi)
try:
    r = requests.get("https://eapi.binance.com/eapi/v1/exchangeInfo", timeout=5).json()
    symbols = r.get("symbols", [])
    btc_options = [s["symbol"] for s in symbols if "BTC" in s.get("symbol", "")]
    print(f"Total Active Binance BTC Options Contracts: {len(btc_options)}")
    if btc_options:
        print("Sample BTC Option contracts:")
        for s in btc_options[:8]:
            print(f"  - {s}")
except Exception as e:
    print("Binance Options error:", e)

print("="*80)
