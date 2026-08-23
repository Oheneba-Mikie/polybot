import math
from dotenv import load_dotenv
import os

load_dotenv("scalper_bailout_deploy/.env")

from py_clob_client_v2 import ClobClient, ApiCreds
from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType

creds = ApiCreds(
    api_key=os.getenv("POLYMARKET_API_KEY"),
    api_secret=os.getenv("POLYMARKET_API_SECRET"),
    api_passphrase=os.getenv("POLYMARKET_API_PASSPHRASE")
)
client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=os.getenv("POLYMARKET_PRIVATE_KEY"),
    creds=creds,
    signature_type=3,
    funder=os.getenv("POLYMARKET_ADDRESS")
)

# Test live collateral balance
resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
print("Collateral resp:", resp)
raw_b = float(resp.get("balance", 0)) / 1_000_000
print(f"USDC Balance: ${raw_b:.4f}")
