import urllib.request
import json
import os
from dotenv import load_dotenv

load_dotenv()

def master_audit():
    print("==========================================================")
    print("       MASTER DOLLAR-FOR-DOLLAR EVERYTHING AUDIT          ")
    print("==========================================================")
    
    addrs = {
        "Account 1 (0x0159...)": "0x0159010e49e7Db204a897819a787f41CFe1F2C67",
        "Bot Funder (0xb579...)": "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8",
        "Binance Deposit (0x4cd0...)": "0x4cd00e387622c35bddb9b4c962c136462338bc31"
    }
    
    # 1. BSC Audit
    rpc_bsc = "https://bsc-rpc.publicnode.com"
    token_bsc_usdc = "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d"
    
    print("\n--- 1. BINANCE SMART CHAIN (BSC) AUDIT ---")
    for name, addr in addrs.items():
        # Native BNB
        p1 = {"jsonrpc": "2.0", "method": "eth_getBalance", "params": [addr, "latest"], "id": 1}
        req = urllib.request.Request(rpc_bsc, data=json.dumps(p1).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        try:
            bnb = int(json.loads(urllib.request.urlopen(req, timeout=5).read().decode('utf-8')).get("result", "0x0"), 16) / 1e18
        except: bnb = 0.0
        
        # BEP20 USDC
        data = f"0x70a08231000000000000000000000000{addr[2:]}"
        p2 = {"jsonrpc": "2.0", "method": "eth_call", "params": [{"to": token_bsc_usdc, "data": data}, "latest"], "id": 2}
        req = urllib.request.Request(rpc_bsc, data=json.dumps(p2).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        try:
            usdc = int(json.loads(urllib.request.urlopen(req, timeout=5).read().decode('utf-8')).get("result", "0x0"), 16) / 1e18
        except: usdc = 0.0
        
        print(f"[{name}]")
        print(f"   USDC Balance: ${usdc:.2f} USDC")
        print(f"   BNB Balance : {bnb:.6f} BNB (~${bnb * 600:.2f} USD)")

    # 2. Polygon Audit
    rpc_poly = "https://polygon-bor-rpc.publicnode.com"
    token_poly_usdc_e = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    token_poly_usdc_native = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
    
    print("\n--- 2. POLYGON NETWORK AUDIT ---")
    for name, addr in addrs.items():
        # Native POL
        p1 = {"jsonrpc": "2.0", "method": "eth_getBalance", "params": [addr, "latest"], "id": 1}
        req = urllib.request.Request(rpc_poly, data=json.dumps(p1).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        try:
            pol = int(json.loads(urllib.request.urlopen(req, timeout=5).read().decode('utf-8')).get("result", "0x0"), 16) / 1e18
        except: pol = 0.0
        
        # USDC.e
        data = f"0x70a08231000000000000000000000000{addr[2:]}"
        p2 = {"jsonrpc": "2.0", "method": "eth_call", "params": [{"to": token_poly_usdc_e, "data": data}, "latest"], "id": 2}
        req = urllib.request.Request(rpc_poly, data=json.dumps(p2).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        try:
            usdc_e = int(json.loads(urllib.request.urlopen(req, timeout=5).read().decode('utf-8')).get("result", "0x0"), 16) / 1e6
        except: usdc_e = 0.0
        
        # Native USDC
        p3 = {"jsonrpc": "2.0", "method": "eth_call", "params": [{"to": token_poly_usdc_native, "data": data}, "latest"], "id": 3}
        req = urllib.request.Request(rpc_poly, data=json.dumps(p3).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        try:
            usdc_nat = int(json.loads(urllib.request.urlopen(req, timeout=5).read().decode('utf-8')).get("result", "0x0"), 16) / 1e6
        except: usdc_nat = 0.0
        
        print(f"[{name}]")
        print(f"   USDC.e Balance : ${usdc_e:.2f} USDC")
        print(f"   Native USDC    : ${usdc_nat:.2f} USDC")
        print(f"   POL Gas Balance: {pol:.6f} POL (~${pol * 0.40:.2f} USD)")

    # 3. Polymarket CLOB Balance
    print("\n--- 3. POLYMARKET LIVE CLOB ACCOUNT ---")
    try:
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import ApiCreds, BalanceAllowanceParams, AssetType
        
        pk = os.getenv("POLYMARKET_PRIVATE_KEY", "0x535a7ea810ec26c77dd75ed03798356c27cb70fcd283782e0411e0d896b56b3f")
        funder = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
        creds = ApiCreds(
            api_key=os.getenv("POLYMARKET_API_KEY", ""),
            api_secret=os.getenv("POLYMARKET_API_SECRET", ""),
            api_passphrase=os.getenv("POLYMARKET_API_PASSPHRASE", "")
        )
        client = ClobClient(host="https://clob.polymarket.com", chain_id=137, key=pk, creds=creds, signature_type=3, funder=funder)
        bal_info = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        poly_usdc = float(bal_info.get("balance", "0")) / 1e6
        print(f"   Polymarket Live Cash: ${poly_usdc:.2f} USDC")
    except Exception as e:
        print(f"   CLOB Error: {e}")
        
    print("\n==========================================================")

if __name__ == "__main__":
    master_audit()
