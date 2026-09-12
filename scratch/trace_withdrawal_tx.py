import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

user_addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
rpc_url = "https://polygon-rpc.com"
usdc_contract = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174" # USDC.e
usdc_native = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359" # Native USDC

print("="*95)
print(f"🔍 TRACING ON-CHAIN WITHDRAWAL TRANSACTION FOR: {user_addr}")
print("="*95)

# Query recent logs for Transfer event from user_addr
# Transfer(address from, address to, uint256 value)
# Topic0: 0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
# Topic1 (from): 0x000000000000000000000000 + user_addr[2:]

topic0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
topic1 = "0x000000000000000000000000" + user_addr[2:].lower()

# Get latest block
r_blk = requests.post(rpc_url, json={"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}, timeout=5).json()
latest_blk = int(r_blk.get("result", "0x0"), 16)
from_blk = hex(latest_blk - 5000) # Past ~2.5 hours

for token_addr, name in [(usdc_contract, "USDC.e"), (usdc_native, "Native USDC")]:
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getLogs",
        "params": [{
            "address": token_addr,
            "topics": [topic0, topic1],
            "fromBlock": from_blk,
            "toBlock": "latest"
        }],
        "id": 2
    }
    try:
        r_logs = requests.post(rpc_url, json=payload, timeout=8).json()
        logs = r_logs.get("result", [])
        print(f"\n📦 {name} Outgoing Transfers in the last ~2 hours ({len(logs)} found):")
        for l in logs:
            tx = l.get("transactionHash")
            to_addr = "0x" + l.get("topics", [""]*3)[2][-40:]
            val = int(l.get("data", "0x0"), 16) / 1e6
            print(f"  • TX: {tx}")
            print(f"    To Address:   {to_addr}")
            print(f"    Amount Sent:  ${val:.4f} {name}")
            print(f"    PolygonScan:  https://polygonscan.com/tx/{tx}")
    except Exception as e:
        print(f"Error querying {name} logs: {e}")

print("="*95)
