import requests
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

wallet = "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"
wallet_clean = "000000000000000000000000" + wallet[2:]

USDC_NATIVE = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
USDC_BRIDGED = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

rpcs = ["https://polygon-rpc.com", "https://rpc.ankr.com/polygon", "https://1rpc.io/matic"]

for name, token_contract in [("Native USDC", USDC_NATIVE), ("Bridged USDC.e", USDC_BRIDGED)]:
    for rpc in rpcs:
        try:
            r = requests.post(rpc, json={
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [{"to": token_contract, "data": "0x70a08231" + wallet_clean}, "latest"],
                "id": 1
            }, timeout=3).json()
            hex_val = r.get("result", "0x0")
            bal = int(hex_val, 16) / 1e6
            print(f"{name} ({rpc}): ${bal:.4f}")
            break
        except Exception as e:
            continue
