import requests

address = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
usdc_contract = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174" # USDC.e on Polygon
usdc_native = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"   # Native USDC on Polygon

print("="*80)
print(f"CHECKING LIVE WALLET BALANCE FOR: {address}")
print("="*80)

# Check via Polygon RPC or Polymarket balance API
rpc_url = "https://polygon-rpc.com"

# ERC20 balanceOf function selector: 0x70a08231 + 32-byte address
padded_addr = address.lower().replace("0x", "").zfill(64)
data = "0x70a08231" + padded_addr

# 1. Check USDC.e
payload1 = {"jsonrpc":"2.0","method":"eth_call","params":[{"to": usdc_contract, "data": data}, "latest"],"id":1}
try:
    r1 = requests.post(rpc_url, json=payload1, timeout=5).json()
    bal_usdc_e = int(r1.get("result", "0x0"), 16) / 1e6
    print(f"USDC.e Balance:  ${bal_usdc_e:.4f} USDC")
except Exception as e:
    bal_usdc_e = 0
    print(f"USDC.e Error: {e}")

# 2. Check Native USDC
payload2 = {"jsonrpc":"2.0","method":"eth_call","params":[{"to": usdc_native, "data": data}, "latest"],"id":2}
try:
    r2 = requests.post(rpc_url, json=payload2, timeout=5).json()
    bal_usdc_nat = int(r2.get("result", "0x0"), 16) / 1e6
    print(f"Native USDC:     ${bal_usdc_nat:.4f} USDC")
except Exception as e:
    bal_usdc_nat = 0
    print(f"Native USDC Error: {e}")

# 3. Check Native POL/MATIC
payload3 = {"jsonrpc":"2.0","method":"eth_getBalance","params":[address, "latest"],"id":3}
try:
    r3 = requests.post(rpc_url, json=payload3, timeout=5).json()
    bal_matic = int(r3.get("result", "0x0"), 16) / 1e18
    print(f"MATIC/POL (Gas): {bal_matic:.4f} POL")
except Exception as e:
    bal_matic = 0
    print(f"MATIC Error: {e}")

total_usdc = bal_usdc_e + bal_usdc_nat
print(f"\nTOTAL AVAILABLE USDC: ${total_usdc:.4f}")
print("="*80)
