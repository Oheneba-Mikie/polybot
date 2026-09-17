import requests

funder = "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"
# USDC Bridged (USDC.e) on Polygon: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174 (used by Polymarket)
# Native USDC: 0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359

# BalanceOf data: 0x70a08231 + 24 zeros + address
addr_padded = funder.lower().replace("0x", "").zfill(64)
data = "0x70a08231" + addr_padded

rpc_url = "https://polygon-bor-rpc.publicnode.com"

for token_name, token_contract in [("USDC.e (Polymarket)", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"), ("Native USDC", "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359")]:
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": token_contract, "data": data}, "latest"],
        "id": 1
    }
    r = requests.post(rpc_url, json=payload, timeout=5).json()
    res = r.get("result", "0x0")
    bal_raw = int(res, 16)
    bal_usdc = bal_raw / 1e6
    print(f"{token_name} Balance: ${bal_usdc:.4f} USDC")
