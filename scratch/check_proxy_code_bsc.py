import urllib.request
import json

def check_proxy():
    proxy_addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    rpc_bsc = "https://bsc-dataseed.binance.org"
    rpc_poly = "https://polygon-bor-rpc.publicnode.com"
    
    # 1. Get Code on BSC
    p1 = {"jsonrpc": "2.0", "method": "eth_getCode", "params": [proxy_addr, "latest"], "id": 1}
    req = urllib.request.Request(rpc_bsc, data=json.dumps(p1).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    code_bsc = json.loads(urllib.request.urlopen(req, timeout=5).read().decode('utf-8')).get("result", "0x")
    
    # 2. Get Code on Polygon
    p2 = {"jsonrpc": "2.0", "method": "eth_getCode", "params": [proxy_addr, "latest"], "id": 2}
    req = urllib.request.Request(rpc_poly, data=json.dumps(p2).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    code_poly = json.loads(urllib.request.urlopen(req, timeout=5).read().decode('utf-8')).get("result", "0x")
    
    print(f"Code on BSC    : {code_bsc[:50]}... (Length: {len(code_bsc)})")
    print(f"Code on Polygon: {code_poly[:50]}... (Length: {len(code_poly)})")

if __name__ == "__main__":
    check_proxy()
