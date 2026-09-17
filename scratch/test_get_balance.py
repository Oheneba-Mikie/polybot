import os, sys
sys.path.append("d:/Desktop/antigravity/POLYBOT/polybot/batch_fok_deploy")
from dotenv import load_dotenv
from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import ApiCreds, BalanceAllowanceParams, AssetType

load_dotenv("d:/Desktop/antigravity/POLYBOT/polybot/batch_fok_deploy/.env")

private_key = os.getenv("POLYMARKET_PRIVATE_KEY", "")
funder = os.getenv("POLYMARKET_ADDRESS", "")
api_key = os.getenv("POLYMARKET_API_KEY", "")
api_secret = os.getenv("POLYMARKET_API_SECRET", "")
api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE", "")

creds = ApiCreds(
    api_key=api_key,
    api_secret=api_secret,
    api_passphrase=api_passphrase,
)
client = ClobClient(
    host="https://clob.polymarket.com",
    key=private_key,
    chain_id=137,
    creds=creds,
    signature_type=2,
    funder=funder,
)

try:
    bal = client.get_balance_allowance(params=BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
    print("BALANCE ALLOWANCE RESULT:", bal)
except Exception as e:
    print("Error:", e)
