import os, sys, requests, json
from dotenv import load_dotenv

load_dotenv()
addr = os.getenv("POLYMARKET_ADDRESS", "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8")

print(f"=== CHECKING BALANCES FOR ADDRESS: {addr} ===")

# 1. Polymarket CLOB Collateral
for sig_type in [0, 1, 2]:
    try:
        r = requests.get(f"https://clob.polymarket.com/balance-allowance?asset_type=COLLATERAL&signature_type={sig_type}&user={addr}", timeout=5).json()
        b_val = float(r.get("balance", "0")) / 1e6
        print(f"Polymarket CLOB Collateral (Sig {sig_type}): ${b_val:.4f} USDC")
    except Exception as e:
        print(f"Polymarket CLOB Collateral (Sig {sig_type}) error: {e}")

# 2. Polymarket Data API Value & Positions
try:
    r_val = requests.get(f"https://data-api.polymarket.com/value?user={addr}", timeout=5).json()
    print(f"Polymarket Data API Portfolio Value: {r_val}")
except Exception as e:
    print(f"Portfolio Value error: {e}")

try:
    r_pos = requests.get(f"https://data-api.polymarket.com/positions?user={addr}", timeout=5).json()
    print(f"Polymarket Open Positions Count: {len(r_pos)}")
    for p in r_pos:
        sz = float(p.get("size", "0"))
        cp = float(p.get("curPrice", "0"))
        if sz > 0:
            print(f"  - Position: {p.get('title', p.get('asset'))} | Outcome: {p.get('outcome')} | Size: {sz:.2f} | CurPrice: ${cp:.4f} | Value: ${sz*cp:.2f}")
except Exception as e:
    print(f"Positions error: {e}")

# 3. On-chain Polygon balances (USDC.e & Native USDC & POL)
polygon_rpcs = ["https://polygon-rpc.com", "https://rpc.ankr.com/polygon"]
for rpc in polygon_rpcs:
    try:
        # USDC.e
        p1 = {"jsonrpc": "2.0", "method": "eth_call", "params": [{"to": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", "data": "0x70a08231000000000000000000000000" + addr[2:]}, "latest"], "id": 1}
        # Native USDC
        p2 = {"jsonrpc": "2.0", "method": "eth_call", "params": [{"to": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", "data": "0x70a08231000000000000000000000000" + addr[2:]}, "latest"], "id": 2}
        # POL / MATIC native
        p3 = {"jsonrpc": "2.0", "method": "eth_getBalance", "params": [addr, "latest"], "id": 3}

        r1 = requests.post(rpc, json=p1, timeout=5).json()
        r2 = requests.post(rpc, json=p2, timeout=5).json()
        r3 = requests.post(rpc, json=p3, timeout=5).json()

        bal_usdce = int(r1.get("result", "0x0"), 16) / 1e6
        bal_usdc = int(r2.get("result", "0x0"), 16) / 1e6
        bal_pol = int(r3.get("result", "0x0"), 16) / 1e18

        print(f"\nOn-Chain Polygon:")
        print(f"  USDC.e (Bridged / Polymarket collateral): ${bal_usdce:.4f}")
        print(f"  Native USDC: ${bal_usdc:.4f}")
        print(f"  POL / MATIC (Gas): {bal_pol:.4f} POL")
        break
    except Exception as e:
        continue
