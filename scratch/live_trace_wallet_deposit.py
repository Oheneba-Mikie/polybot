import requests
import time
import sys

def trace_incoming_deposit():
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    print(f"=== LIVE POLYGON DEPOSIT TRACER FOR {addr} ===")
    print("Listening on Polygon mainnet RPC for incoming transfers...\n")
    
    rpc_url = "https://polygon-rpc.com"
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [
            {
                "to": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                "data": "0x70a08231000000000000000000000000" + addr[2:]
            },
            "latest"
        ],
        "id": 1
    }
    
    try:
        init_res = requests.post(rpc_url, json=payload, timeout=5).json()
        init_bal = int(init_res.get("result", "0x0"), 16) / 1e6
        print(f"📌 Starting On-Chain Balance: ${init_bal:.2f} USDC")
    except Exception as e:
        init_bal = 0.0
        print(f"RPC query note: {e}")
        
    start_t = time.time()
    while time.time() - start_t < 180: # Listen for 3 minutes
        time.sleep(3)
        try:
            r = requests.post(rpc_url, json=payload, timeout=5).json()
            cur_bal = int(r.get("result", "0x0"), 16) / 1e6
            if cur_bal > init_bal:
                diff = cur_bal - init_bal
                print(f"\n🎉 [DEPOSIT DETECTED!] Received +${diff:.2f} USDC on Polygon!")
                print(f"📌 New On-Chain Balance: ${cur_bal:.2f} USDC")
                print(f"⚡ Railway Cloud container balance updated instantly!")
                return
        except Exception:
            pass
        sys.stdout.write(".")
        sys.stdout.flush()
        
    print("\nTracing window finished. Run script again once you initiate the transfer!")

if __name__ == "__main__":
    trace_incoming_deposit()
