import requests

BSC_RPC = "https://bsc-dataseed.binance.org"
tx_hash = "0xf68b083c827d985b79441b79df1de4e722001e4b07ee8a5cfa2eecd2017e8a3a"

payload = {
    "jsonrpc": "2.0",
    "method": "eth_getTransactionReceipt",
    "params": [tx_hash],
    "id": 1
}

r = requests.post(BSC_RPC, json=payload, timeout=5).json()
receipt = r.get("result", {})

print("="*60)
print("BSC TRANSACTION DETAILS:")
print("="*60)
print("Status:", "SUCCESS" if receipt.get("status") == "0x1" else "FAILED/PENDING")
print("To:", receipt.get("to"))
print("From:", receipt.get("from"))
print("Logs count:", len(receipt.get("logs", [])))
