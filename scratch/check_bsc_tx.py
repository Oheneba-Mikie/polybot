import urllib.request
import json

def check_bsc_tx():
    tx_hash = "0xc2410a1a08cc162e8b16dcc344ea6adee22305a624f3c98b1b44acb4a6f495cf"
    print(f"=== DECODING BSC TRANSACTION {tx_hash} ===")
    
    bsc_rpcs = [
        "https://binance.llamarpc.com",
        "https://bsc-dataseed.binance.org",
        "https://bsc-rpc.publicnode.com"
    ]
    
    for rpc in bsc_rpcs:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionReceipt",
            "params": [tx_hash],
            "id": 1
        }
        req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
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
                
                # Check ERC20 Transfer log
                for log in logs:
                    # Transfer event signature = 0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
                    topics = log.get("topics", [])
                    if len(topics) >= 3 and topics[0] == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef":
                        sender = "0x" + topics[1][-40:]
                        recipient = "0x" + topics[2][-40:]
                        raw_val = int(log.get("data", "0x0"), 16)
                        
                        # Check decimals (18 for BSC-USD / 6 for USDC)
                        token_contract = log.get("address")
                        print(f"\n⚡ ERC20 TRANSFER LOG:")
                        print(f"   Token Contract: {token_contract}")
                        print(f"   Sender: {sender}")
                        print(f"   Recipient: {recipient}")
                        print(f"   Raw Amount: {raw_val} (Decimals: {raw_val / 1e18:.2f} if 18 decimals, {raw_val / 1e6:.2f} if 6 decimals)")
                return
        except Exception as e:
            print(f"RPC {rpc} error: {e}")

if __name__ == "__main__":
    check_bsc_tx()
