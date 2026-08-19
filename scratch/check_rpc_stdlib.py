import json
import urllib.request

addrs = {
    "Bot Funder / Configured Address": "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8",
    "Account 1": "0x0159010e49e7Db204a897819a787f41CFe1F2C67"
}

def query_rpc(url, method, params, req_id=1):
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": req_id}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {"error": str(e)}

poly_rpc = "https://polygon-bor-rpc.publicnode.com"
bsc_rpc = "https://bsc-dataseed1.binance.org/"

for name, addr in addrs.items():
    print(f"\n==========================================")
    print(f"[{name}] {addr}")
    print(f"==========================================")
    data_call = "0x70a08231000000000000000000000000" + addr[2:]
    
    # Polygon
    r_pol = query_rpc(poly_rpc, "eth_getBalance", [addr, "latest"], 1)
    pol_bal = int(r_pol.get("result", "0x0"), 16) / 1e18 if "result" in r_pol else 0.0

    r_usdce = query_rpc(poly_rpc, "eth_call", [{"to": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", "data": data_call}, "latest"], 2)
    usdce_bal = int(r_usdce.get("result", "0x0"), 16) / 1e6 if "result" in r_usdce else 0.0

    r_usdc = query_rpc(poly_rpc, "eth_call", [{"to": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", "data": data_call}, "latest"], 3)
    usdc_bal = int(r_usdc.get("result", "0x0"), 16) / 1e6 if "result" in r_usdc else 0.0

    print(f"POLYGON:")
    print(f"  - USDC.e (Polymarket Collateral): ${usdce_bal:.4f}")
    print(f"  - Native USDC: ${usdc_bal:.4f}")
    print(f"  - POL (Gas): {pol_bal:.6f} POL")

    # BSC
    r_bnb = query_rpc(bsc_rpc, "eth_getBalance", [addr, "latest"], 4)
    bnb_bal = int(r_bnb.get("result", "0x0"), 16) / 1e18 if "result" in r_bnb else 0.0

    r_bsc_usdc = query_rpc(bsc_rpc, "eth_call", [{"to": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", "data": data_call}, "latest"], 6)
    bsc_usdc_bal = int(r_bsc_usdc.get("result", "0x0"), 16) / 1e18 if "result" in r_bsc_usdc else 0.0

    print(f"BSC:")
    print(f"  - BNB (Gas): {bnb_bal:.6f} BNB")
    print(f"  - BSC-USDC: ${bsc_usdc_bal:.4f}")
