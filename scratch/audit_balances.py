import urllib.request
import json
from eth_account import Account
import os
from dotenv import load_dotenv

load_dotenv("batch_fok_deploy/.env")

pk = os.getenv("POLYMARKET_PRIVATE_KEY")
signer = Account.from_key(pk).address if pk else "None"
funder = os.getenv("FUNDER", os.getenv("POLYMARKET_ADDRESS", ""))

print(f"Signer (EOA): {signer}")
print(f"Funder (Proxy): {funder}")

# Check on-chain balances
tokens = {
    "USDC.e (0x2791...)": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    "Native USDC (0x3c49...)": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
    "POL / MATIC": "NATIVE"
}

rpcs = ["https://polygon.llamarpc.com", "https://rpc.ankr.com/polygon", "https://1rpc.io/matic"]

def call_rpc(payload):
    for rpc in rpcs:
        try:
            req = urllib.request.Request(rpc, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            res = json.loads(urllib.request.urlopen(req, timeout=4).read().decode())
            if "result" in res:
                return res["result"]
        except Exception:
            continue
    return "0x0"

for name, addr in [("Funder (Proxy)", funder), ("Signer (EOA)", signer)]:
    if not addr: continue
    print(f"\n--- Balances for {name}: {addr} ---")
    # Native
    nat_hex = call_rpc({"jsonrpc": "2.0", "method": "eth_getBalance", "params": [addr, "latest"], "id": 1})
    print(f"  POL / MATIC: {int(nat_hex, 16) / 1e18:.4f}")
    for t_name, t_contract in tokens.items():
        if t_contract == "NATIVE": continue
        data = "0x70a08231000000000000000000000000" + addr[2:].lower()
        res_hex = call_rpc({"jsonrpc": "2.0", "method": "eth_call", "params": [{"to": t_contract, "data": data}, "latest"], "id": 1})
        val = int(res_hex, 16) / 1e6
        print(f"  {t_name}: ${val:.2f}")
