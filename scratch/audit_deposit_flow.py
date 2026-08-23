import requests
import json

POLYMARKET_ADDRESS = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
EOA_ADDRESS = "0x0159010e49e7Db204a897819a787f41CFe1F2C67"

# Check Polygonscan / Data API for deposit transfers
r_trans = requests.get(f"https://data-api.polymarket.com/activity?user={POLYMARKET_ADDRESS}&limit=20").json()

print("="*80)
print("AUDITING TODAY'S TOP-UP & TRANSFERS:")
print("="*80)
for a in r_trans:
    if a.get("type") in ["DEPOSIT", "TRANSFER", "REDEEM"]:
        print(f"Type: {a.get('type')} | Amount: ${a.get('usdcSize')} | Title: {a.get('title')} | Tx: {a.get('transactionHash')}")

# Also check EOA on Polygon
POLYGON_RPC = "https://polygon-rpc.com"
def get_matic_bal(addr):
    p = {"jsonrpc": "2.0", "method": "eth_getBalance", "params": [addr, "latest"], "id": 1}
    res = requests.post(POLYGON_RPC, json=p).json().get("result", "0x0")
    return int(res, 16) / 1e18

print("\nMATIC Balances:")
print(f"Proxy ({POLYMARKET_ADDRESS}): {get_matic_bal(POLYMARKET_ADDRESS):.4f} MATIC")
print(f"EOA   ({EOA_ADDRESS}):        {get_matic_bal(EOA_ADDRESS):.4f} MATIC")
