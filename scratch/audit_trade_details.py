import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

user_addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
DATA_HOST = "https://data-api.polymarket.com"

print("="*95)
print("🔍 DEEP AUDIT: EXAMINING THE 18:12:12 UTC & 18:14:49 UTC TRADES IN DETAIL")
print("="*95)

# Query recent trades with full JSON details
r = requests.get(f"{DATA_HOST}/trades?user={user_addr}&limit=5").json()

for idx, t in enumerate(r[:2], 1):
    print(f"\n--- TRADE #{idx} FULL DETAILS ---")
    print(f"Timestamp:        {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(t.get('timestamp', 0)))}")
    print(f"Market Title:     {t.get('title')}")
    print(f"Side:             {t.get('side')}")
    print(f"Outcome:          {t.get('outcome')}")
    print(f"Shares:           {t.get('size')} shares")
    print(f"Price per Share:  ${t.get('price')}")
    print(f"Transaction Hash: {t.get('transactionHash')}")
    print(f"Maker / Taker:    {t.get('type')}")
    print(f"Order ID / Match: {t.get('matchId', 'CLOB Match')}")

print("="*95)
