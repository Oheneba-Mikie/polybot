import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

addr = "0x639f7e0b317f586b350cdcc1ceb22a2ed44e2211"
rpc_url = "https://polygon-bor-rpc.publicnode.com"

print("="*95)
print(f"🔍 INSPECTING RECIPIENT ADDRESS: {addr}")
print("="*95)

# Check if contract or EOA
p_code = {"jsonrpc":"2.0","method":"eth_getCode","params":[addr, "latest"],"id":1}
r_code = requests.post(rpc_url, json=p_code, timeout=5).json()
code = r_code.get("result", "0x")
is_contract = code != "0x" and len(code) > 2
print(f"Address Type: {'Smart Contract' if is_contract else 'EOA (Personal Wallet / Exchange Account)'}")

# Check USDC balance at this address
usdc_contract = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
payload = {
    "jsonrpc": "2.0",
    "method": "eth_call",
    "params": [{
        "to": usdc_contract,
        "data": "0x70a08231000000000000000000000000" + addr[2:]
    }, "latest"],
    "id": 2
}
r_bal = requests.post(rpc_url, json=payload, timeout=5).json()
bal = int(r_bal.get("result", "0x0"), 16) / 1e6
print(f"Current USDC Balance at {addr}: ${bal:.4f} USDC")
print("="*95)
