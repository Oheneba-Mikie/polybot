import os, sys
from dotenv import load_dotenv
from py_clob_client_v2 import ClobClient, ApiCreds
from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
import requests

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("scalper_bailout_deploy/.env")

POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS")

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
    funder=POLYMARKET_ADDRESS
)

# 1. Check CLOB collateral balance
resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
raw_b = float(resp.get("balance", 0)) / 1_000_000

# 2. Check Polygon RPC USDC balance for EOA and Proxy
r_act = requests.get(f"https://data-api.polymarket.com/activity?user={POLYMARKET_ADDRESS}&limit=3").json()

print("="*60)
print(f"CURRENT POLYMARKET CASH BALANCE: ${raw_b:.4f} USDC")
print("="*60)
print("Recent Activity on Polymarket:")
for a in r_act:
    print(f"  • {a.get('type')} | {a.get('title')} | ${float(a.get('usdcSize') or 0):.2f}")
