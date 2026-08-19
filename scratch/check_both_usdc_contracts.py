import urllib.request
import json

def check_both_usdc():
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    print(f"=== CHECKING BOTH USDC CONTRACTS FOR {addr} ===")
    
    # 1. Native USDC: 0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359
    # 2. Bridged USDC.e: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
    
    usdc_contracts = {
        "Native USDC (0x3c49...)": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        "Bridged USDC.e (0x2791...)": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    }
    
    rpc = "https://1rpc.io/matic"
    
    for name, c_addr in usdc_contracts.items():
        # balanceOf(address) signature = 0x70a08231
        data = f"0x70a08231000000000000000000000000{addr[2:]}"
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": c_addr, "data": data}, "latest"],
            "id": 1
        }
        
        req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        try:
            res = urllib.request.urlopen(req, timeout=5)
            r_json = json.loads(res.read().decode('utf-8'))
            hex_val = r_json.get("result", "0x0")
            val = int(hex_val, 16) / 1e6
            print(f"{name}: ${val:.4f} USDC")
        except Exception as e:
            print(f"{name} Query Error: {e}")

if __name__ == "__main__":
    check_both_usdc()
