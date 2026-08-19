import requests

def check_portfolio():
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    print(f"=== FULL PORTFOLIO QUERY FOR {addr} ===")
    
    # 1. Check open positions
    r1 = requests.get(f"https://data-api.polymarket.com/positions?user={addr}").json()
    print(f"\n1. Open Positions (Total: {len(r1)}):")
    for pos in r1:
        print(f"   Asset: {pos.get('asset')} | Size: {pos.get('size')} | Outcome: {pos.get('outcome')} | Current Price: ${pos.get('curPrice')}")
        
    # 2. Check recent trades
    r2 = requests.get(f"https://data-api.polymarket.com/trades?user={addr}&limit=10").json()
    print(f"\n2. Recent Trades (Total: {len(r2)}):")
    for tr in r2[:10]:
        print(f"   Side: {tr.get('side')} | Price: ${tr.get('price')} | Size: {tr.get('size')} | Asset: {tr.get('asset')} | Timestamp: {tr.get('timestamp')}")

    # 3. Check CTF / Collateral balance across all signature types
    for sig_type in [0, 1, 2]:
        r3 = requests.get(f"https://clob.polymarket.com/balance-allowance?asset_type=COLLATERAL&signature_type={sig_type}&user={addr}").json()
        b_val = float(r3.get("balance", "0")) / 1e6
        print(f"3. Collateral Balance (Sig Type {sig_type}): ${b_val:.2f} USDC")

if __name__ == "__main__":
    check_portfolio()
