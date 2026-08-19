import urllib.request
import json

def check_all_bnb():
    addrs = {
        "Account 1 (0x0159...)": "0x0159010e49e7Db204a897819a787f41CFe1F2C67",
        "Proxy Funder (0xb579...)": "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    }
    
    rpc = "https://bsc-dataseed1.binance.org"
    print("=== CHECKING BNB BALANCE ON ALL ADDRESSES ===")
    
    for label, addr in addrs.items():
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [addr, "latest"],
            "id": 1
        }
        req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        try:
            res = urllib.request.urlopen(req, timeout=5)
            r_json = json.loads(res.read().decode('utf-8'))
            val = int(r_json.get("result", "0x0"), 16) / 1e18
            print(f"{label}: {val:.6f} BNB (~${val * 600:.4f} USD)")
        except Exception as e:
            print(f"{label} Error: {e}")

if __name__ == "__main__":
    check_all_bnb()
