import urllib.request
import json

def decode_polygon_tx():
    tx_hash = "0xa69f3d18e3d5958ade31cee8a279ac5e444d097d3fcfe7c59b772836168192e1"
    print(f"=== DECODING POLYGON TRANSACTION {tx_hash} ===")
    
    rpcs = [
        "https://polygon.drpc.org",
        "https://polygon-bor-rpc.publicnode.com",
        "https://1rpc.io/matic"
    ]
    
    for rpc in rpcs:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionReceipt",
            "params": [tx_hash],
            "id": 1
        }
        req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        try:
            res = urllib.request.urlopen(req, timeout=5)
            r_json = json.loads(res.read().decode('utf-8'))
            receipt = r_json.get("result")
            if receipt:
                status = receipt.get("status")
                from_addr = receipt.get("from")
                to_addr = receipt.get("to")
                logs = receipt.get("logs", [])
                
                print(f"Status: {'SUCCESS (1)' if status == '0x1' else 'FAILED (0)'}")
                print(f"From: {from_addr}")
                print(f"To: {to_addr}")
                print(f"Logs Count: {len(logs)}")
                
                for log in logs:
                    topics = log.get("topics", [])
                    if len(topics) >= 3 and topics[0] == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef":
                        sender = "0x" + topics[1][-40:]
                        recipient = "0x" + topics[2][-40:]
                        raw_val = int(log.get("data", "0x0"), 16)
                        token_contract = log.get("address")
                        
                        print(f"\n--- ERC20 TRANSFER LOG ---")
                        print(f"   Token Contract: {token_contract}")
                        print(f"   Sender: {sender}")
                        print(f"   Recipient: {recipient}")
                        print(f"   Amount (6 decimals): ${raw_val / 1e6:.4f} USDC")
                        print(f"   Amount (18 decimals): ${raw_val / 1e18:.4f} USDC")
                return
        except Exception as e:
            print(f"RPC {rpc} error: {e}")

if __name__ == "__main__":
    decode_polygon_tx()
