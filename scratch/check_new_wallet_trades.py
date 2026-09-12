import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

addr = "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"
try:
    r = requests.get(f"https://data-api.polymarket.com/trades?user={addr}&limit=10").json()
    print("Trades for new wallet:")
    print(json.dumps(r, indent=2))
except Exception as e:
    print("Error:", e)
