import urllib.request
import json

def check_mempool():
    tx_hash = "0x34b542b42324cdcad6298b14bd1753f61eff23547d8d9434990acbe7fd72d396"
    print(f"=== CHECKING MEMPOOL STATUS FOR {tx_hash} ===")
    
    rpc = "https://bsc-rpc.publicnode.com"
    payload = {"jsonrpc": "2.0", "method": "eth_getTransactionByHash", "params": [tx_hash], "id": 1}
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    
    res = urllib.request.urlopen(req, timeout=5)
    tx = json.loads(res.read().decode('utf-8')).get("result")
    if tx:
        print("Tx Found In Mempool/Chain!")
        print("Block Number:", tx.get("blockNumber"))
        print("From:", tx.get("from"))
        print("To:", tx.get("to"))
        print("Nonce:", int(tx.get("nonce", "0x0"), 16))
    else:
        print("Tx not found in mempool.")

if __name__ == "__main__":
    check_mempool()
