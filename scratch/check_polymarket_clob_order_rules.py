import requests
import json

def check_clob_rules():
    print("=== TESTING POLYMARKET CLOB MINIMUM ORDER RULES ===")
    
    # Query Gamma API for active binary market metadata
    r = requests.get("https://gamma-api.polymarket.com/events?limit=5&active=true&closed=false").json()
    if not r:
        print("No active event found.")
        return
        
    mkt = r[0]["markets"][0]
    tokens = json.loads(mkt.get("clobTokenIds", "[]"))
    token_id = tokens[0]
    
    # Fetch CLOB order book for token
    r_book = requests.get(f"https://clob.polymarket.com/book?token_id={token_id}").json()
    min_order_size = r_book.get("min_order_size", "5")
    tick_size = r_book.get("tick_size", "0.01")
    
    print(f"Token ID: {token_id[:16]}...")
    print(f"CLOB min_order_size: {min_order_size} shares")
    print(f"CLOB tick_size: {tick_size}")
    
    # Test 1: Minimum shares required by API = float(min_order_size)
    min_shares = float(min_order_size) # 5.0 shares
    
    print(f"\n1. Official Polymarket CLOB Rule: Minimum Order Size is {min_shares:.0f} shares.")
    
    # Example 1: 5 shares @ 0.10 (Cost = $0.50) -> Valid!
    # Example 2: 5 shares @ 0.20 (Cost = $1.00) -> Valid!
    # Example 3: 5 shares @ 0.35 (Cost = $1.75) -> Valid for $2.20 cash!
    # Example 4: 5 shares @ 0.95 (Cost = $4.75) -> Requires $4.75 cash.
    
    print("\n2. Cost for 5 Shares at Different Price Levels:")
    for p in [0.01, 0.05, 0.10, 0.20, 0.30, 0.35, 0.70, 0.95]:
        cost = min_shares * p
        fits = "YES (Fits $2.20 cash!)" if cost <= 2.20 else "NO (Requires $" + f"{cost:.2f} cash)"
        print(f"  * Price ${p:.2f} -> 5 Shares Cost = ${cost:.2f} | Fits $2.20 Cash? {fits}")

if __name__ == "__main__":
    check_clob_rules()
