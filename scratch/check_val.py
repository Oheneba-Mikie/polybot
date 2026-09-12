import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
user_addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"

try:
    r = requests.get(f"https://data-api.polymarket.com/value?user={user_addr}").json()
    print("Polymarket Portfolio Value Endpoint:", r)
except Exception as e:
    print("Value error:", e)
