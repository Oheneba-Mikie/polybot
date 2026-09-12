import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

tx_hash = "0xe0f1df7f9ec7c50ddb905d5c5ce587d77048a89bff7621de43890c9ee4983dbd"
rpc_url = "https://polygon-bor-rpc.publicnode.com"

print("="*95)
print(f"🔬 FULL ON-CHAIN FORENSIC DECODER FOR TRANSACTION: {tx_hash}")
print("="*95)

# 1. Fetch TX
p_tx = {"jsonrpc":"2.0","method":"eth_getTransactionByHash","params":[tx_hash],"id":1}
r_tx = requests.post(rpc_url, json=p_tx, timeout=8).json().get("result", {})

# 2. Fetch Receipt
p_rc = {"jsonrpc":"2.0","method":"eth_getTransactionReceipt","params":[tx_hash],"id":2}
r_rc = requests.post(rpc_url, json=p_rc, timeout=8).json().get("result", {})

# 3. Fetch Block Timestamp
blk_num = r_tx.get("blockNumber")
p_blk = {"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":[blk_num, False],"id":3}
r_blk = requests.post(rpc_url, json=p_blk, timeout=8).json().get("result", {})

blk_ts = int(r_blk.get("timestamp", "0x0"), 16)
dt_utc = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(blk_ts))

print(f"📅 Exact Time (UTC):     {dt_utc}")
print(f"🧱 Block Number:         {int(blk_num, 16)}")
print(f"⛽ Gas Used:             {int(r_rc.get('gasUsed', '0x0'), 16):,} gas")
print(f"👤 Relayer / Submitter:  {r_tx.get('from')} (Polymarket Gas Relayer)")
print(f"🏢 Contract Called:      {r_tx.get('to')} (Polymarket Proxy Factory / Relayer)")
print(f"⚙️ Method Selector:       {r_tx.get('input')[:10]}")

input_data = r_tx.get("input", "")
print(f"\n📦 Raw Calldata Length:  {len(input_data)} bytes")

# Extract transfer details from logs
for idx, log in enumerate(r_rc.get("logs", []), 1):
    contract = log.get("address")
    topics = log.get("topics", [])
    data = log.get("data", "0x0")
    if topics and topics[0] == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef":
        fr = "0x" + topics[1][-40:]
        to = "0x" + topics[2][-40:]
        val = int(data, 16) / 1e6
        print(f"\n💸 Action Executed in Log #{idx}:")
        print(f"   • Asset:        USDC (Contract: {contract})")
        print(f"   • Source (From): 0x{topics[1][-40:]}")
        print(f"   • Target (To):   0x{topics[2][-40:]}")
        print(f"   • Amount:       ${val:.4f} USDC")

print("="*95)
