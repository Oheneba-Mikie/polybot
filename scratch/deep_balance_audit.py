import requests
import json
from eth_account import Account

pk = "0x535a7ea810ec26c77dd75ed03798356c27cb70fcd283782e0411e0d896b56b3f"
eoa_account = Account.from_key(pk)
eoa_address = eoa_account.address
proxy_address = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"

print("="*80)
print(f"EOA (Signer) Address:  {eoa_address}")
print(f"Proxy Wallet Address:  {proxy_address}")
print("="*80)

# 1. Check positions on Polymarket for Proxy
r_pos_proxy = requests.get(f"https://data-api.polymarket.com/positions?user={proxy_address}").json()
print(f"Open Positions for Proxy ({proxy_address}):")
print(json.dumps(r_pos_proxy, indent=2))

# 2. Check positions on Polymarket for EOA
r_pos_eoa = requests.get(f"https://data-api.polymarket.com/positions?user={eoa_address}").json()
print(f"\nOpen Positions for EOA ({eoa_address}):")
print(json.dumps(r_pos_eoa, indent=2))

# 3. Check USDC on Polygon for EOA
rpc_url = "https://polygon-rpc.com"
usdc_e = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
usdc_nat = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"

def check_addr_usdc(addr, name):
    padded = addr.lower().replace("0x", "").zfill(64)
    data = "0x70a08231" + padded
    tot = 0
    for c, cname in [(usdc_e, "USDC.e"), (usdc_nat, "Native USDC")]:
        try:
            p = {"jsonrpc":"2.0","method":"eth_call","params":[{"to": c, "data": data}, "latest"],"id":1}
            res = requests.post(rpc_url, json=p, timeout=4).json()
            val = int(res.get("result", "0x0"), 16) / 1e6
            tot += val
            print(f"  {name} {cname}: ${val:.4f}")
        except Exception as e:
            print(f"  Error {cname}: {e}")
    return tot

print("\n--- ON-CHAIN USDC BALANCES ---")
check_addr_usdc(proxy_address, "Proxy")
check_addr_usdc(eoa_address, "EOA")
