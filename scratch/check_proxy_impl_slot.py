import urllib.request
import json

def check_impl_slot():
    proxy = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    rpc = "https://polygon-bor-rpc.publicnode.com"
    
    print(f"=== CHECKING EIP-1967 IMPLEMENTATION SLOT FOR {proxy} ===")
    
    slot_eip1967 = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
    payload = {"jsonrpc": "2.0", "method": "eth_getStorageAt", "params": [proxy, slot_eip1967, "latest"], "id": 1}
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    res = urllib.request.urlopen(req, timeout=5)
    s_impl = json.loads(res.read().decode('utf-8')).get("result")
    print("EIP-1967 Implementation Slot:", s_impl)

if __name__ == "__main__":
    check_impl_slot()
