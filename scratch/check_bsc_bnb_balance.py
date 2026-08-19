import urllib.request
import json

def check_bnb():
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    rpc = "https://bsc-dataseed1.binance.org"
    
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [addr, "latest"],
        "id": 1
    }
    
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        res = urllib.request.urlopen(req, timeout=5)
        hex_val = json.loads(res.read().decode('utf-8')).get("result", "0x0")
        val = int(hex_val, 16) / 1e18
        print(f"=== BSC BNB BALANCE FOR {addr} ===")
        print(f"BNB Balance: {val:.6f} BNB (~${val * 600:.4f} USD)")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_bnb()
