import requests
import datetime

def full_audit():
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    print(f"=== FULL CHRONOLOGICAL DOLLAR-BY-DOLLAR AUDIT FOR {addr} ===")
    
    r = requests.get(f"https://data-api.polymarket.com/trades?user={addr}&limit=30").json()
    
    # Sort trades chronologically by timestamp
    trades = sorted(r, key=lambda x: int(x.get("timestamp", 0)))
    
    print(f"Total Transactions Found: {len(trades)}\n")
    
    for i, t in enumerate(trades):
        ts = int(t.get("timestamp", 0))
        dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M:%S UTC")
        side = t.get("side")
        price = float(t.get("price", "0"))
        size = float(t.get("size", "0"))
        usdc_val = float(t.get("usdcSize", "0"))
        outcome = t.get("outcome", "N/A")
        title = t.get("title", "Market")
        
        print(f"{i+1:2d}. [{dt_str}] {side:4s} | {size:.1f} shares @ ${price:.2f} | Total: ${usdc_val:.2f} | Outcome: {outcome}")

if __name__ == "__main__":
    full_audit()
