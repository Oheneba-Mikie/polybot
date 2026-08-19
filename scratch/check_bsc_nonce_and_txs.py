import urllib.request
import json

def check_nonce_txs():
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    print(f"=== CHECKING BSC NONCE & TRANSACTIONS FOR {addr} ===")
    
    rpc = "https://bsc-rpc.publicnode.com"
    
    payload = {"jsonrpc": "2.0", "method": "eth_getTransactionCount", "params": [addr, "latest"], "id": 1}
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    res = urllib.request.urlopen(req, timeout=5)
    nonce = int(json.loads(res.read().decode('utf-8'))["result"], 16)
    print(f"Latest Confirmed Nonce: {nonce}")
    
    payload = {"jsonrpc": "2.0", "method": "eth_getTransactionCount", "params": [addr, "pending"], "id": 2}
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    res = urllib.request.urlopen(req, timeout=5)
    p_nonce = int(json.loads(res.read().decode('utf-8'))["result"], 16)
    print(f"Pending Nonce: {p_nonce}")

if __name__ == "__main__":
    check_nonce_txs()
