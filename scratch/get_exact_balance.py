import os
from dotenv import load_dotenv
from py_clob_client_v2 import ClobClient, ApiCreds, BalanceAllowanceParams, AssetType
import sys

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv("scalper_bailout_deploy/.env")

creds = ApiCreds(
    api_key=os.getenv("POLYMARKET_API_KEY", ""),
    api_secret=os.getenv("POLYMARKET_API_SECRET", ""),
    api_passphrase=os.getenv("POLYMARKET_API_PASSPHRASE", "")
)
client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=os.getenv("POLYMARKET_PRIVATE_KEY", ""),
    creds=creds,
    signature_type=3,
    funder=os.getenv("POLYMARKET_ADDRESS", "")
)

params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
b = client.get_balance_allowance(params)
bal = float(b.get("balance", 0)) / 1e6

print("="*60)
print(f"💵 EXACT CURRENT WALLET BALANCE: ${bal:.4f} USDC")
print("="*60)
