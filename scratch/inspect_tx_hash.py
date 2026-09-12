import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

tx_hash = "0xe0f1df7f9ec7c50ddb905d5c5ce587d77048a89bff7621de43890c9ee4983dbd"
rpc_url = "https://polygon-rpc.com"

print("="*95)
print(f"🔍 FORENSIC ON-CHAIN INSPECTION OF TRANSACTION: {tx_hash}")
print("="*95)

# 1. eth_getTransactionByHash
p_tx = {"jsonrpc":"2.0","method":"eth_getTransactionByHash","params":[tx_hash],"id":1}
r_tx = requests.post(rpc_url, json=p_tx, timeout=8).json()
tx_data = r_tx.get("result", {})

print(f"From (Signer / Relayer): {tx_data.get('from')}")
print(f"To (Contract Interacted): {tx_data.get('to')}")
print(f"Block Number:             {int(tx_data.get('blockNumber', '0x0'), 16)}")
print(f"Value (Native MATIC/POL): {int(tx_data.get('value', '0x0'), 16) / 1e18:.6f} POL")

# 2. eth_getTransactionReceipt
p_rc = {"jsonrpc":"2.0","method":"eth_getTransactionReceipt","params":[tx_hash],"id":2}
r_rc = requests.post(rpc_url, json=p_rc, timeout=8).json()
rc_data = r_rc.get("result", {})

status = int(rc_data.get("status", "0x0"), 16)
print(f"Status:                   {'SUCCESS (1)' if status == 1 else 'FAILED (0)'}")

print("\n--- ERC-20 / TOKEN TRANSFER LOGS IN THIS TX ---")
for idx, log in enumerate(rc_data.get("logs", []), 1):
    contract = log.get("address")
    topics = log.get("topics", [])
    data = log.get("data", "0x0")
    if topics and topics[0] == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef": # Transfer
        fr_addr = "0x" + topics[1][-40:]
        to_addr = "0x" + topics[2][-40:]
        val = int(data, 16) / 1e6
        print(f"  [{idx}] Transfer on Contract {contract}:")
        print(f"      From:   {fr_addr}")
        print(f"      To:     {to_addr}")
        print(f"      Amount: ${val:.4f} USDC")

print("="*95)
