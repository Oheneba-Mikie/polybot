import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

WALLET = "0x89B489569F1B2384ee02E958444aF6091219bfe9"
CTF = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045" # ConditionalTokens
RPC_URL = "https://polygon-bor-rpc.publicnode.com"

print("="*90)
print(f"🔍 CHECKING CTF PAYOUT REDEMPTIONS FOR WALLET: {WALLET}")
print("="*90)

# PayoutRedemption topic on CTF: PayoutRedemption(address indexed redeemer, address indexed collateralToken, bytes32 indexed parentCollectionId, bytes32 conditionId, uint256[] indexSets, uint256 payout)
# Topic0: 0x3d280c4436573c09b8221b6d0e82c58988636f328f643f11043ef6ff79a52e00
REDEMPTION_TOPIC = "0x3d280c4436573c09b8221b6d0e82c58988636f328f643f11043ef6ff79a52e00"
wallet_topic = "0x000000000000000000000000" + WALLET[2:].lower()

res_block = requests.post(RPC_URL, json={"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}, timeout=5).json()
latest_block = int(res_block["result"], 16)
from_block = hex(latest_block - 200000)

payload = {
    "jsonrpc": "2.0",
    "method": "eth_getLogs",
    "params": [{
        "address": CTF,
        "fromBlock": from_block,
        "toBlock": "latest",
        "topics": [REDEMPTION_TOPIC, wallet_topic]
    }],
    "id": 2
}

try:
    r = requests.post(RPC_URL, json=payload, timeout=10).json()
    logs = r.get("result", [])
    print(f"CTF Payout Redemptions found: {len(logs)}")
    for l in logs:
        tx_h = l.get("transactionHash", "")
        block_n = int(l.get("blockNumber", "0"), 16)
        data = l.get("data", "")
        # payout is in data
        # let's parse payout
        cid = l["topics"][3] if len(l.get("topics",[]))>3 else ""
        print(f"- Block {block_n} | Condition: {cid[:18]}... | Tx: {tx_h}")
except Exception as e:
    print(f"Error: {e}")

print("="*90)
