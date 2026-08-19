import os
from dotenv import load_dotenv

load_dotenv()

def check_polymarket_balance():
    pk = os.getenv("POLYMARKET_PRIVATE_KEY", "0x535a7ea810ec26c77dd75ed03798356c27cb70fcd283782e0411e0d896b56b3f")
    addr = os.getenv("POLYMARKET_ADDRESS", "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8")
    
    print(f"=== QUERYING POLYMARKET CLOB BALANCE FOR {addr} ===")
    
    try:
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import ApiCreds, BalanceAllowanceParams, AssetType
        
        creds = ApiCreds(
            api_key=os.getenv("POLYMARKET_API_KEY", ""),
            api_secret=os.getenv("POLYMARKET_API_SECRET", ""),
            api_passphrase=os.getenv("POLYMARKET_API_PASSPHRASE", "")
        )
        
        client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=137,
            key=pk,
            creds=creds,
            signature_type=3,
            funder=addr
        )
        
        bal_info = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        print("CLOB Balance Allowance Response:", bal_info)
        b_val = float(bal_info.get("balance", "0")) / 1e6
        print(f"Polymarket Live Cash Balance: ${b_val:.4f} USDC")
        
    except Exception as e:
        print(f"Error querying CLOB client: {e}")

if __name__ == "__main__":
    check_polymarket_balance()
