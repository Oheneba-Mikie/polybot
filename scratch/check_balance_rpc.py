import requests
import json

def check_rpc():
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    print(f"=== CHECKING ON-CHAIN USDC BALANCE VIA POLYGON RPC ===")
    
    # Backup Polygon RPC endpoints
    rpcs = [
        "https://polygon-bor-rpc.publicnode.com",
        "https://1rpc.io/matic",
        "https://polygon.gateway.tenderly.co"
    ]
    
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [
            {
                "to": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", # USDC.e
                "data": "0x70a08231000000000000000000000000" + addr[2:]
            },
            "latest"
        ],
        "id": 1
    }
    
    for rpc in rpcs:
        try:
            r = requests.post(rpc, json=payload, timeout=4).json()
            raw = r.get("result", "0x0")
            bal = int(raw, 16) / 1e6
            print(f"RPC ({rpc.split('/')[2]}): USDC.e Balance = ${bal:.4f} USDC")
            break
        except Exception as e:
            print(f"RPC {rpc.split('/')[2]} failed: {e}")

if __name__ == "__main__":
    check_rpc()
