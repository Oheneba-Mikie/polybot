import os
from dotenv import load_dotenv
from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import ApiCreds, BalanceAllowanceParams, AssetType
import requests

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

print("Funder Address:", funder)

# Method 1: Data API
try:
    r = requests.get(f"https://data-api.polymarket.com/value?user={funder}").json()
    print("Data API /value:", r)
except Exception as e:
    print("Data API error:", e)

# Method 2: Polymarket Profile / Value API
try:
    r_pos = requests.get(f"https://data-api.polymarket.com/positions?user={funder}").json()
    print(f"Active Positions: {len(r_pos)}")
except Exception as e:
    print("Positions error:", e)

# Method 3: CLOB get_balance_allowance
try:
    resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
    print("CLOB Balance Allowance:", resp)
    if resp and "balance" in resp:
        print("Live CLOB Balance:", float(resp["balance"]) / 1e6)
except Exception as e:
    print("CLOB balance error:", e)
