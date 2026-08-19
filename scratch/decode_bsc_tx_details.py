import urllib.request
import json

def decode_bsc_tx_details():
    tx_hash = "0xc2410a1a08cc162e8b16dcc344ea6adee22305a624f3c98b1b44acb4a6f495cf"
    print("=== DECODING BSC TX DETAILS ===")
    
    rpc = "https://bsc-dataseed1.binance.org"
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getTransactionReceipt",
        "params": [tx_hash],
        "id": 1
    }
    
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        res = urllib.request.urlopen(req, timeout=5)
        receipt = json.loads(res.read().decode('utf-8')).get("result", {})
        logs = receipt.get("logs", [])
        
        for log in logs:
            topics = log.get("topics", [])
            if len(topics) >= 3:
                sender = "0x" + topics[1][-40:]
                recipient = "0x" + topics[2][-40:]
                raw_val = int(log.get("data", "0x0"), 16)
                
                print(f"Status: SUCCESS")
                print(f"Token Contract (BSC): {log.get('address')}")
                print(f"Sender Address: {sender}")
                print(f"Recipient Address: {recipient}")
                print(f"Amount Transferred (18 decimals): ${raw_val / 1e18:.4f} USDC")
                print(f"Amount Transferred (6 decimals): ${raw_val / 1e6:.4f} USDC")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    decode_bsc_tx_details()
