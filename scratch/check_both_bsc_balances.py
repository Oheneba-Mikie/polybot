import urllib.request
import json

def check_both_bsc():
    addrs = {
        "Address 1 (0x0159... - EOA Wallet)": "0x0159010e49e7Db204a897819a787f41CFe1F2C67",
        "Address 2 (0xb579... - Proxy Funder)": "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    }
    
    token = "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d" # BSC-USD
    rpc = "https://bsc-dataseed1.binance.org"
    
    print("=== CHECKING BSC-USD BALANCE ON BOTH ADDRESSES ===")
    
    for label, addr in addrs.items():
        data = f"0x70a08231000000000000000000000000{addr[2:]}"
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": token, "data": data}, "latest"],
            "id": 1
        }
        req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        try:
            res = urllib.request.urlopen(req, timeout=5)
            r_json = json.loads(res.read().decode('utf-8'))
            val = int(r_json.get("result", "0x0"), 16) / 1e18
            print(f"{label}: ${val:.4f} USDC")
        except Exception as e:
            print(f"{label} Error: {e}")

if __name__ == "__main__":
    check_both_bsc()
