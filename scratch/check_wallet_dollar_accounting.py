import requests

def check_wallet():
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    r = requests.get(f"https://clob.polymarket.com/balance-allowance?asset_type=COLLATERAL&signature_type=0&user={addr}").json()
    bal = float(r.get("balance", "0")) / 1e6
    print(f"ON-CHAIN USDC COLLATERAL BALANCE FOR {addr}: ${bal:.2f} USDC")

if __name__ == "__main__":
    check_wallet()
