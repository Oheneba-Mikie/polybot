import urllib.request
import json

def check_proxy_storage():
    proxy = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    rpc = "https://polygon-bor-rpc.publicnode.com"
    
    print(f"=== CHECKING PROXY STORAGE SLOTS FOR {proxy} ===")
    
    # Slot 0
    payload = {"jsonrpc": "2.0", "method": "eth_getStorageAt", "params": [proxy, "0x0", "latest"], "id": 1}
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    res = urllib.request.urlopen(req, timeout=5)
    s0 = json.loads(res.read().decode('utf-8')).get("result")
    print("Slot 0 (MasterCopy / Implementation):", s0)

if __name__ == "__main__":
    check_proxy_storage()
