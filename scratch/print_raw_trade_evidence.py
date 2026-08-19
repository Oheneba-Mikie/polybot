import requests
import json

def print_raw_evidence():
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    print("=== RAW POLYMARKET ON-CHAIN TRADE DATA ===")
    r = requests.get(f"https://data-api.polymarket.com/trades?user={addr}&limit=10").json()
    
    for i, t in enumerate(r):
        print(f"Trade #{i+1}: Side={t.get('side')} | Price=${t.get('price')} | Size={t.get('size')} | Time={t.get('timestamp')}")

if __name__ == "__main__":
    print_raw_evidence()
