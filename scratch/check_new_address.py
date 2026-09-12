import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

new_addr = "0x5930bD966dDE405285146382456942A9632eC694"
print("="*80)
print(f"🔍 CHECKING NEW ADDRESS ON POLYMARKET GAMMA API: {new_addr}")
print("="*80)

try:
    r = requests.get(f"https://gamma-api.polymarket.com/users/{new_addr}", timeout=5).json()
    print("Gamma User Profile Response:")
    print(json.dumps(r, indent=2))
except Exception as e:
    print("Gamma API Error / Not initialized yet:", e)

print("="*80)
