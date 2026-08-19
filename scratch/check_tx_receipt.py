import urllib.request
import json

def check_receipt():
    tx_hash = "0x34b542b42324cdcad6298b14bd1753f61eff23547d8d9434990acbe7fd72d396"
    print(f"=== CHECKING TX RECEIPT {tx_hash} ===")
    
    rpc = "https://bsc-dataseed.binance.org"
    payload = {"jsonrpc": "2.0", "method": "eth_getTransactionReceipt", "params": [tx_hash], "id": 1}
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    
    res = urllib.request.urlopen(req, timeout=5)
    receipt = json.loads(res.read().decode('utf-8')).get("result", {})
    if receipt:
        status = receipt.get("status")
        print(f"On-Chain Status: {'SUCCESS (1)' if status == '0x1' else 'FAILED (0)'}")
        print(f"Block Number: {int(receipt.get('blockNumber', '0x0'), 16)}")
        print(f"Gas Used: {int(receipt.get('gasUsed', '0x0'), 16)}")

if __name__ == "__main__":
    check_receipt()
