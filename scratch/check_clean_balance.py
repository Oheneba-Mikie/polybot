import requests

def get_balance():
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    rpc_url = "https://polygon-rpc.com"
    
    # USDC.e contract: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
    payload_usdce = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [
            {
                "to": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                "data": "0x70a08231000000000000000000000000" + addr[2:]
            },
            "latest"
        ],
        "id": 1
    }
    
    # Native USDC contract: 0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359
    payload_usdc = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [
            {
                "to": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
                "data": "0x70a08231000000000000000000000000" + addr[2:]
            },
            "latest"
        ],
        "id": 2
    }
    
    r1 = requests.post(rpc_url, json=payload_usdce).json()
    r2 = requests.post(rpc_url, json=payload_usdc).json()
    
    bal1 = int(r1.get("result", "0x0"), 16) / 1e6
    bal2 = int(r2.get("result", "0x0"), 16) / 1e6
    
    print(f"ON-CHAIN BALANCE FOR {addr}:")
    print(f"USDC.e  = ${bal1:.6f}")
    print(f"USDC    = ${bal2:.6f}")

if __name__ == "__main__":
    get_balance()
