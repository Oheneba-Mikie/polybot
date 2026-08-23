import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Check Polygon USDC balance via public RPC
POLYGON_RPC = "https://polygon-rpc.com"
USDC_NATIVE = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
USDC_BRIDGED = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
WALLET = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"

def get_erc20_balance(contract, wallet):
    # balanceOf(address) selector: 0x70a08231
    padded_addr = wallet[2:].lower().rjust(64, '0')
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": contract, "data": "0x70a08231" + padded_addr}, "latest"],
        "id": 1
    }
    r = requests.post(POLYGON_RPC, json=payload, timeout=5).json()
    hex_val = r.get("result", "0x0")
    raw = int(hex_val, 16) if hex_val != "0x" else 0
    return raw / 1_000_000

usdc_n = get_erc20_balance(USDC_NATIVE, WALLET)
usdc_b = get_erc20_balance(USDC_BRIDGED, WALLET)

print(f"Native Polygon USDC:  ${usdc_n:.4f}")
print(f"Bridged USDC (USDC.e): ${usdc_b:.4f}")
