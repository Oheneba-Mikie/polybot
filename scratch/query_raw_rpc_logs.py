import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

WALLET = "0x89B489569F1B2384ee02E958444aF6091219bfe9"
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174" # Bridged USDC on Polygon

# Polygon Public RPC
RPC_URL = "https://polygon-bor-rpc.publicnode.com"

print("="*90)
print(f"🔍 PULLING RAW ON-CHAIN ERC20 TRANSFER LOGS FOR: {WALLET}")
print("="*90)

# Transfer topic
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
wallet_topic = "0x000000000000000000000000" + WALLET[2:].lower()

# Query latest block
res_block = requests.post(RPC_URL, json={"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}, timeout=5).json()
latest_block = int(res_block["result"], 16)
from_block = hex(latest_block - 100000) # last ~100k blocks (~2 days)

# Query incoming transfers
payload_in = {
    "jsonrpc": "2.0",
    "method": "eth_getLogs",
    "params": [{
        "fromBlock": from_block,
        "toBlock": "latest",
        "topics": [TRANSFER_TOPIC, None, wallet_topic]
    }],
    "id": 2
}

try:
    r_in = requests.post(RPC_URL, json=payload_in, timeout=10).json()
    logs_in = r_in.get("result", [])
    print(f"Incoming transfers in last 48h: {len(logs_in)}")
    for l in logs_in:
        contract = l.get("address", "")
        tx_h = l.get("transactionHash", "")
        block_n = int(l.get("blockNumber", "0"), 16)
        raw_val = int(l.get("data", "0"), 16)
        val = raw_val / 1_000_000 # 6 decimals
        from_acc = "0x" + l["topics"][1][-40:]
        print(f"- Block {block_n} | +${val:.4f} USDC | From: {from_acc} | Contract: {contract} | Tx: {tx_h}")
except Exception as e:
    print(f"Error querying RPC logs: {e}")

print("="*90)
