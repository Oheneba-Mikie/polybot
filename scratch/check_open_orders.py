import os
import requests
import json
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("d:/Desktop/antigravity/POLYBOT/polybot/scalper_bailout_deploy/.env")

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2 import ApiCreds
from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType

POLYMARKET_ADDRESS        = os.getenv("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY        = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET     = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY    = os.getenv("POLYMARKET_PRIVATE_KEY", "")

creds = ApiCreds(
    api_key=POLYMARKET_API_KEY,
    api_secret=POLYMARKET_API_SECRET,
    api_passphrase=POLYMARKET_API_PASSPHRASE
)
client = ClobClient(
    host="https://clob.polymarket.com",
    key=POLYMARKET_PRIVATE_KEY,
    chain_id=137,
    creds=creds,
    signature_type=3,
    funder=POLYMARKET_ADDRESS
)

print("="*90)
print("🔍 CHECKING OPEN ORDERS & PENDING LOCKS ON CLOB:")
print("="*90)

# Check open orders
try:
    orders = client.get_open_orders()
    print(f"Total Open Orders on CLOB: {len(orders)}")
    for o in orders:
        oid = o.get("orderID", "")[:15]
        side = o.get("side", "")
        sz = float(o.get("original_size", 0))
        px = float(o.get("price", 0))
        print(f"- Order {oid}... | Side: {side} | {sz:.2f} shares @ ${px:.4f}")
except Exception as e:
    print(f"Error fetching open orders: {e}")

# Check cash balance
bal_col = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
cash_bal = float(bal_col.get("balance", 0)) / 1_000_000
print(f"\n💵 Available Free Collateral: ${cash_bal:.4f} USDC")
print("="*90)
