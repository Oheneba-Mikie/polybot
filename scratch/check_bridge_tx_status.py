import urllib.request
import json

def check_bridge_tx():
    tx_hash = "0x45dc6a58f7f4f1efe78ed9cc330e8933e9f3ac5a8d42fd62d92b609b64a27166"
    print(f"=== CHECKING BRIDGE TX {tx_hash} ON BSCSCAN & LI.FI ===")
    
    # 1. Check BSC TX Status
    rpc = "https://bsc-rpc.publicnode.com"
    payload = {"jsonrpc": "2.0", "method": "eth_getTransactionReceipt", "params": [tx_hash], "id": 1}
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    try:
        res = urllib.request.urlopen(req, timeout=5)
        receipt = json.loads(res.read().decode('utf-8')).get("result", {})
        if receipt:
            status = receipt.get("status")
            print(f"BSC On-Chain Status: {'SUCCESS (1)' if status == '0x1' else 'FAILED / PENDING'}")
            print(f"Block Number: {int(receipt.get('blockNumber', '0x0'), 16)}")
    except Exception as e:
        print(f"BSC RPC Error: {e}")
        
    # 2. Check Li.Fi Status
    url = f"https://li.quest/v1/status?txHash={tx_hash}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        res = urllib.request.urlopen(req, timeout=5)
        status_json = json.loads(res.read().decode('utf-8'))
        print("Li.Fi Bridge Status:", status_json.get("status"))
        print("Substatus:", status_json.get("substatusMsg"))
    except Exception as e:
        print(f"Li.Fi Status Error: {e}")

if __name__ == "__main__":
    check_bridge_tx()
