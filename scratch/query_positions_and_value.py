import requests
import json

proxy_address = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"

print("="*80)
print(f"CHECKING POLYMARKET POSITIONS & ON-CHAIN TOKENS FOR: {proxy_address}")
print("="*80)

# 1. Polymarket Positions
try:
    r_pos = requests.get(f"https://data-api.polymarket.com/positions?user={proxy_address}").json()
    print("Open Positions on Polymarket:")
    print(json.dumps(r_pos, indent=2))
except Exception as e:
    print("Positions error:", e)

# 2. Polymarket Activity / Value
try:
    r_val = requests.get(f"https://data-api.polymarket.com/value?user={proxy_address}").json()
    print("\nAccount Portfolio Value:")
    print(json.dumps(r_val, indent=2))
except Exception as e:
    print("Portfolio value error:", e)

# 3. Polygon RPC Check
rpc_url = "https://polygon-rpc.com"
usdc_e = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
usdc_nat = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
padded = proxy_address.lower().replace("0x", "").zfill(64)
data = "0x70a08231" + padded

for c, name in [(usdc_e, "USDC.e"), (usdc_nat, "Native USDC")]:
    p = {"jsonrpc":"2.0","method":"eth_call","params":[{"to": c, "data": data}, "latest"],"id":1}
    r = requests.post(rpc_url, json=p, timeout=4).json()
    val = int(r.get("result", "0x0"), 16) / 1e6
    print(f"On-Chain {name}: ${val:.4f}")
