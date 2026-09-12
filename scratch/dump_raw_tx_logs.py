import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

tx_hash = "0xe0f1df7f9ec7c50ddb905d5c5ce587d77048a89bff7621de43890c9ee4983dbd"
rpc_url = "https://polygon-bor-rpc.publicnode.com"

print("="*95)
print(f"📜 COMPLETE RAW ON-CHAIN LOG DUMP FOR TRANSACTION: {tx_hash}")
print("="*95)

# 1. eth_getTransactionByHash
p_tx = {"jsonrpc":"2.0","method":"eth_getTransactionByHash","params":[tx_hash],"id":1}
r_tx = requests.post(rpc_url, json=p_tx, timeout=8).json().get("result", {})

# 2. eth_getTransactionReceipt
p_rc = {"jsonrpc":"2.0","method":"eth_getTransactionReceipt","params":[tx_hash],"id":2}
r_rc = requests.post(rpc_url, json=p_rc, timeout=8).json().get("result", {})

# 3. Block details
blk_num = r_tx.get("blockNumber")
p_blk = {"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":[blk_num, False],"id":3}
r_blk = requests.post(rpc_url, json=p_blk, timeout=8).json().get("result", {})
blk_ts = int(r_blk.get("timestamp", "0x0"), 16)
dt_utc = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(blk_ts))

print(f"1. TRANSACTION SUMMARY:")
print(f"   • Timestamp:          {dt_utc}")
print(f"   • Block Number:       {int(blk_num, 16)}")
print(f"   • Transaction Hash:   {tx_hash}")
print(f"   • Sender / Relayer:   {r_tx.get('from')} (Polymarket Gas Relayer)")
print(f"   • Contract Called:    {r_tx.get('to')} (Polymarket: Deposit Wallet Factory Proxy)")
print(f"   • Gas Used:           {int(r_rc.get('gasUsed', '0x0'), 16):,} gas")
print(f"   • Status:             {'SUCCESS (Code 1)' if int(r_rc.get('status', '0x0'), 16) == 1 else 'FAILED'}")

print(f"\n2. RAW CALLDATA INPUT:")
print(f"   • Method Selector:    {r_tx.get('input')[:10]}")
print(f"   • Full Input Hex:     {r_tx.get('input')[:130]}... [Total {len(r_tx.get('input'))} characters]")

print(f"\n3. ALL 4 EVENT LOGS EMITTED IN THIS TRANSACTION:")
for idx, log in enumerate(r_rc.get("logs", []), 1):
    contract = log.get("address")
    topics = log.get("topics", [])
    data = log.get("data", "0x0")
    print(f"\n   --- EVENT LOG #{idx} ---")
    print(f"   • Emitted By Contract: {contract}")
    print(f"   • Topic 0 (Event ID): {topics[0] if len(topics) > 0 else 'None'}")
    for t_i, t_val in enumerate(topics[1:], 1):
        print(f"   • Topic {t_i} (Indexed): {t_val}")
    print(f"   • Data:               {data}")
    
    # Check if ERC-20 Transfer
    if topics and topics[0] == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef":
        fr = "0x" + topics[1][-40:]
        to = "0x" + topics[2][-40:]
        val = int(data, 16) / 1e6
        print(f"   ➡️ DECODED ACTION: ERC-20 Transfer of ${val:.4f} USDC from {fr} to {to}")

print("="*95)
