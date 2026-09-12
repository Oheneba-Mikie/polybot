import os
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("scalper_bailout_deploy/.env")

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import ApiCreds, BalanceAllowanceParams, AssetType

key = os.getenv("POLYMARKET_PRIVATE_KEY")
addr = os.getenv("POLYMARKET_ADDRESS")
creds = ApiCreds(
    api_key=os.getenv("POLYMARKET_API_KEY"),
    api_secret=os.getenv("POLYMARKET_API_SECRET"),
    api_passphrase=os.getenv("POLYMARKET_API_PASSPHRASE")
)

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=key,
    creds=creds,
    signature_type=int(os.getenv("SIGNATURE_TYPE", 3)),
    funder=addr
)

print("="*80)
print("🔍 TESTING NEW POLYMARKET ACCOUNT CONNECTION & BALANCE:")
print(f"   Signer: {os.getenv('POLYMARKET_PRIVATE_KEY')[:10]}...")
print(f"   Proxy:  {addr}")
print("="*80)

resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=3))
raw_b = float(resp.get("balance", 0)) / 1_000_000

print(f"✅ CONNECTION SUCCESSFUL!")
print(f"💰 Current USDC Balance on Polymarket: ${raw_b:.2f} USDC")
print(f"📄 Full Response: {resp}")
print("="*80)
