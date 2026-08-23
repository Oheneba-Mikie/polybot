import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

BSC_RPC = "https://bsc-dataseed.binance.org"
PREDICTION_BNB = "0x18B2A687610328590Bc8F2e5fEdDe3b582A49cdA"

# Function selector for currentEpoch(): 0x759c8695
payload_epoch = {
    "jsonrpc": "2.0",
    "method": "eth_call",
    "params": [{"to": PREDICTION_BNB, "data": "0x759c8695"}, "latest"],
    "id": 1
}

r = requests.post(BSC_RPC, json=payload_epoch, timeout=5).json()
current_epoch = int(r.get("result", "0x0"), 16)

print("="*80)
print("LIVE PANCAKESWAP 5-MINUTE PREDICTION CONTRACT (BNB CHAIN):")
print("="*80)
print(f"Contract Address:   {PREDICTION_BNB}")
print(f"Current Live Epoch: #{current_epoch}")

# Query current epoch details: rounds(uint256) selector: 0xd09de08a
epoch_hex = hex(current_epoch)[2:].rjust(64, '0')
payload_round = {
    "jsonrpc": "2.0",
    "method": "eth_call",
    "params": [{"to": PREDICTION_BNB, "data": "0xd09de08a" + epoch_hex}, "latest"],
    "id": 2
}

r2 = requests.post(BSC_RPC, json=payload_round, timeout=5).json()
data_hex = r2.get("result", "")[2:]
if len(data_hex) >= 64 * 9:
    chunks = [data_hex[i:i+64] for i in range(0, len(data_hex), 64)]
    epoch_id = int(chunks[0], 16)
    start_t  = int(chunks[1], 16)
    lock_t   = int(chunks[2], 16)
    close_t  = int(chunks[3], 16)
    total_amt = int(chunks[6], 16) / 1e18
    bull_amt  = int(chunks[7], 16) / 1e18
    bear_amt  = int(chunks[8], 16) / 1e18
    
    time_left = lock_t - time.time()
    print(f"Round Status:       {'ACCEPTING BETS' if time_left > 0 else 'LOCKED / RESOLVING'}")
    print(f"Time Until Lock:    {time_left:.1f}s")
    print(f"Total Prize Pool:   {total_amt:.4f} BNB (~${total_amt*695:.2f} USD)")
    print(f"Bull Pool (UP):     {bull_amt:.4f} BNB")
    print(f"Bear Pool (DOWN):   {bear_amt:.4f} BNB")
print("="*80)
