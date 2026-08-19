import requests
import json

def deep_check():
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    print(f"=== DEEP POLYMARKET UI & ACCOUNT QUERY FOR {addr} ===")
    
    # 1. Query Polymarket Portfolio Value API (Exact UI numbers)
    try:
        r_val = requests.get(f"https://data-api.polymarket.com/value?user={addr}").json()
        print(f"\n1. Polymarket UI Portfolio Value Endpoint:")
        print(json.dumps(r_val, indent=2))
    except Exception as e:
        print(f"Error querying value: {e}")

    # 2. Query Polymarket Open / Unredeemed Positions
    try:
        r_pos = requests.get(f"https://data-api.polymarket.com/positions?user={addr}").json()
        print(f"\n2. Open / Unredeemed Positions (Total: {len(r_pos)}):")
        total_open_value = 0.0
        for p in r_pos:
            sz = float(p.get("size", "0"))
            cp = float(p.get("curPrice", "0"))
            val = sz * cp
            total_open_value += val
            if sz > 0 and cp > 0:
                print(f"   Asset: {p.get('title', p.get('asset'))[:40]} | Size: {sz:.2f} | Price: ${cp:.3f} | Value: ${val:.2f}")
        print(f"   Total Value of Active/Unredeemed Positions: ${total_open_value:.2f}")
    except Exception as e:
        print(f"Error querying positions: {e}")

    # 3. Query Recent Activity (Fills, Redemptions, Transfers)
    try:
        r_act = requests.get(f"https://data-api.polymarket.com/activity?user={addr}&limit=10").json()
        print(f"\n3. Recent Activity Log (Total: {len(r_act)}):")
        for a in r_act[:10]:
            print(f"   Type: {a.get('type')} | Side: {a.get('side')} | Size: {a.get('size')} | Price: ${a.get('price')} | USVal: ${a.get('usdcSize')} | Time: {a.get('timestamp')}")
    except Exception as e:
        print(f"Error querying activity: {e}")

if __name__ == "__main__":
    deep_check()
