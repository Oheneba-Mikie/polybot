import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

user_addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
DATA_HOST = "https://data-api.polymarket.com"

print("="*95)
print("🔍 ON-CHAIN BALANCE & ACTIVITY CHECK FOR ADDRESS:", user_addr)
print("="*95)

# Check Data API activity
r_act = requests.get(f"{DATA_HOST}/activity?user={user_addr}&limit=10").json()
print("Recent Activity on Polymarket:")
for a in r_act:
    dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(a.get("timestamp", 0)))
    typ = a.get("type")
    amt = a.get("usdcSize") or a.get("size")
    title = a.get("title") or a.get("asset")
    side = a.get("side", "")
    print(f"  [{dt}] Type: {typ} | Size/Amount: {amt} | Side: {side} | Market: {title}")

# Check native USDC balance on Polygon via public RPC
rpc_url = "https://polygon-rpc.com"
usdc_contract = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174" # USDC.e (PoS)
usdc_native = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359" # Native USDC

payload1 = {
    "jsonrpc": "2.0",
    "method": "eth_call",
    "params": [{
        "to": usdc_contract,
        "data": "0x70a08231000000000000000000000000" + user_addr[2:]
    }, "latest"],
    "id": 1
}

payload2 = {
    "jsonrpc": "2.0",
    "method": "eth_call",
    "params": [{
        "to": usdc_native,
        "data": "0x70a08231000000000000000000000000" + user_addr[2:]
    }, "latest"],
    "id": 2
}

try:
    r1 = requests.post(rpc_url, json=payload1, timeout=5).json()
    b1 = int(r1.get("result", "0x0"), 16) / 1e6
    r2 = requests.post(rpc_url, json=payload2, timeout=5).json()
    b2 = int(r2.get("result", "0x0"), 16) / 1e6
    print(f"\n🌐 Direct Polygon RPC Balances:")
    print(f"  • USDC.e (Bridged / Polymarket Collateral): ${b1:.4f} USDC")
    print(f"  • Native USDC:                             ${b2:.4f} USDC")
except Exception as e:
    print("RPC Error:", e)

print("="*95)
