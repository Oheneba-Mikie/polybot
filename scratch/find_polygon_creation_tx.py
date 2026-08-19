import urllib.request
import json

def find_creation():
    proxy = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    rpc = "https://polygon-bor-rpc.publicnode.com"
    
    print(f"=== SEARCHING CREATION LOGS FOR {proxy} ===")
    
    topic_proxy = "0x" + "00"*12 + proxy[2:].lower()
    
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getLogs",
        "params": [{"topics": [None, topic_proxy], "fromBlock": "0x2500000", "toBlock": "latest"}],
        "id": 1
    }
    
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    try:
        res = urllib.request.urlopen(req, timeout=10)
        logs = json.loads(res.read().decode('utf-8')).get("result", [])
        print(f"Found {len(logs)} Creation Logs!")
        if logs:
            print("Creation Tx Hash:", logs[0].get("transactionHash"))
            print("Block Number:", int(logs[0].get("blockNumber", "0x0"), 16))
    except Exception as e:
        print("RPC Error:", e)

if __name__ == "__main__":
    find_creation()
