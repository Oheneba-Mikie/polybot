import requests
import json

def check_activity():
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    print(f"=== CHECKING RECENT POLYMARKET ACTIVITY FOR {addr} ===")
    
    url = f"https://data-api.polymarket.com/activity?user={addr}&limit=10"
    r = requests.get(url).json()
    
    for a in r:
        print(f"Type: {a.get('type')} | Side: {a.get('side')} | Size: {a.get('size')} | Price: ${a.get('price')} | USVal: ${a.get('usdcSize')} | Time: {a.get('timestamp')}")

if __name__ == "__main__":
    check_activity()
