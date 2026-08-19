import requests

def get_onchain_usdc(address):
    rpc_url = "https://polygon-rpc.com"
    usdc_contract = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174" # USDC.e
    usdc_native = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"   # Native USDC
    
    padded_addr = address.lower().replace("0x", "").zfill(64)
    data = "0x70a08231" + padded_addr
    
    bal_total = 0.0
    for contract in (usdc_contract, usdc_native):
        try:
            payload = {"jsonrpc":"2.0","method":"eth_call","params":[{"to": contract, "data": data}, "latest"],"id":1}
            r = requests.post(rpc_url, json=payload, timeout=4).json()
            if "result" in r and r["result"] != "0x":
                bal_total += int(r["result"], 16) / 1e6
        except Exception:
            pass
    return bal_total

addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
print("Live On-Chain USDC Balance:", get_onchain_usdc(addr))
