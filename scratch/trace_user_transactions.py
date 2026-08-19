import requests

def trace_txs():
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    rpc_url = "https://polygon-rpc.com"
    
    tx1 = "0xe8d29df88d771135b0b07ae4d11f4a35f95b36e24a6cd09a160a5b5fda1b1f24"
    tx2 = "0xbb77f4da17ae583a0000d1c81ff3f7d07cc604e2801034cff0a1cb795af9cf24"
    
    print("=== TRACING USER POLYGON TRANSACTIONS ===")
    
    for name, tx in [("Transaction 1", tx1), ("Transaction 2", tx2)]:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionReceipt",
            "params": [tx],
            "id": 1
        }
        r = requests.post(rpc_url, json=payload).json()
        rec = r.get("result")
        if rec:
            status = int(rec.get("status", "0x0"), 16)
            block = int(rec.get("blockNumber", "0x0"), 16)
            print(f"{name} ({tx[:12]}...): Status={'SUCCESS' if status == 1 else 'FAILED'} | Block={block}")
        else:
            print(f"{name} ({tx[:12]}...): Receipt Pending / Indexing...")

    # Query current CLOB balance via Polymarket API
    print(f"\n=== POLYMARKET CLOB ACCOUNT BALANCE FOR {addr} ===")
    try:
        r_act = requests.get(f"https://data-api.polymarket.com/activity?user={addr}&limit=5").json()
        print("Recent Activity:")
        for a in r_act:
            print(f"  Type: {a.get('type')} | Size: {a.get('size')} | Price: ${a.get('price')} | USVal: ${a.get('usdcSize')} | Time: {a.get('timestamp')}")
    except Exception as e:
        print(f"Activity error: {e}")

if __name__ == "__main__":
    trace_txs()
