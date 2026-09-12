import os
import json
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("d:/Desktop/antigravity/POLYBOT/polybot/scalper_bailout_deploy/.env")

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2 import ApiCreds
from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType

KEY    = os.getenv("POLYMARKET_PRIVATE_KEY", "")
API_KEY= os.getenv("POLYMARKET_API_KEY", "")
SECRET = os.getenv("POLYMARKET_API_SECRET", "")
PASS   = os.getenv("POLYMARKET_API_PASSPHRASE", "")
ENV_ADDR = os.getenv("POLYMARKET_ADDRESS", "")

creds = ApiCreds(api_key=API_KEY, api_secret=SECRET, api_passphrase=PASS)

print("="*90)
print("🔍 ADDRESS DISCREPANCY AUDIT:")
print("="*90)
print(f"Address in .env: {ENV_ADDR}")
print("-" * 90)

# Check Wallet 1 (0x89B489569F1B2384ee02E958444aF6091219bfe9)
ADDR_1 = "0x89B489569F1B2384ee02E958444aF6091219bfe9"
try:
    c1 = ClobClient(host="https://clob.polymarket.com", key=KEY, chain_id=137, creds=creds, signature_type=3, funder=ADDR_1)
    b1 = c1.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
    val1 = float(b1.get("balance", 0)) / 1_000_000
    print(f"Wallet 1 ({ADDR_1}): ${val1:.6f} USDC")
except Exception as e:
    print(f"Wallet 1 error: {e}")

# Check Wallet 2 (0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8)
ADDR_2 = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
try:
    c2 = ClobClient(host="https://clob.polymarket.com", key=KEY, chain_id=137, creds=creds, signature_type=3, funder=ADDR_2)
    b2 = c2.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
    val2 = float(b2.get("balance", 0)) / 1_000_000
    print(f"Wallet 2 ({ADDR_2}): ${val2:.6f} USDC")
except Exception as e:
    print(f"Wallet 2 error: {e}")

print("="*90)
