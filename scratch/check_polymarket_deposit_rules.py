import requests

def check_deposit_rules():
    print("=== POLYMARKET DEPOSIT & WALLET RULES CHECK ===")
    
    # 1. Check Polymarket CLOB balance-allowance API
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    url = f"https://clob.polymarket.com/balance-allowance?asset_type=COLLATERAL&signature_type=0&user={addr}"
    r = requests.get(url).json()
    print("1. CLOB Balance Allowance Endpoint Response:")
    print(r)
    
    # 2. Check Polymarket relayer / bridge endpoints if available
    try:
        r2 = requests.get("https://gamma-api.polymarket.com/config").json()
        print("\n2. Gamma Config Endpoint Response:")
        print(r2)
    except Exception as e:
        print(f"Config check: {e}")

if __name__ == "__main__":
    check_deposit_rules()
