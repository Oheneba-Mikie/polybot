import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

tx_hash = "0xe0f1df7f9ec7c50ddb905d5c5ce587d77048a89bff7621de43890c9ee4983dbd"

rpcs = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/matic",
    "https://polygon.llamarpc.com",
    "https://rpc.ankr.com/polygon"
]

print("="*95)
print(f"🔍 MULTI-RPC QUERY FOR TX: {tx_hash}")
print("="*95)

found = False
for rpc in rpcs:
    try:
        p_tx = {"jsonrpc":"2.0","method":"eth_getTransactionByHash","params":[tx_hash],"id":1}
        r_tx = requests.post(rpc, json=p_tx, timeout=5).json()
        tx = r_tx.get("result")
        if tx:
            print(f"✅ Found on {rpc}:")
            print(f"   From:       {tx.get('from')}")
            print(f"   To:         {tx.get('to')}")
            print(f"   Block:      {int(tx.get('blockNumber', '0x0'), 16)}")
            print(f"   Input Data: {tx.get('input')[:70]}...")
            
            p_rc = {"jsonrpc":"2.0","method":"eth_getTransactionReceipt","params":[tx_hash],"id":2}
            r_rc = requests.post(rpc, json=p_rc, timeout=5).json()
            rc = r_rc.get("result", {})
            for idx, log in enumerate(rc.get("logs", []), 1):
                topics = log.get("topics", [])
                data = log.get("data", "0x0")
                if topics and topics[0] == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef":
                    fr = "0x" + topics[1][-40:]
                    to = "0x" + topics[2][-40:]
                    val = int(data, 16) / 1e6
                    print(f"   [Log {idx}] Transfer: {val:.4f} USDC from {fr} to {to}")
            found = True
            break
    except Exception as e:
        print(f"RPC {rpc} error: {e}")

if not found:
    print("Could not locate on public RPCs yet.")
print("="*95)
