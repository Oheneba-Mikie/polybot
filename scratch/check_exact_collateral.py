import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

WALLET = "0x89B489569F1B2384ee02E958444aF6091219bfe9"

# Let's check Polygonscan / Etherscan API or Polygon public RPC logs
# Polygon RPC
RPC_URL = "https://polygon-rpc.com"

# Check token balances directly on RPC
# USDC.e (Bridged): 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
# Native USDC: 0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359
# Polymarket CTF Exchange: 0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2 import ApiCreds
from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
import os
from dotenv import load_dotenv

load_dotenv("d:/Desktop/antigravity/POLYBOT/polybot/scalper_bailout_deploy/.env")

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
    funder=WALLET
)

print("="*80)
print("🔍 EXACT COLLATERAL BREAKDOWN FROM CLOB:")
print("="*80)

resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
print(json.dumps(resp, indent=2))
raw_b = float(resp.get("balance", 0)) / 1_000_000
allowance = float(resp.get("allowance", 0)) / 1_000_000
print(f"\nExact Cash Balance: ${raw_b:.6f} USDC")
print(f"Allowance Approved:  ${allowance:.2f} USDC")
print("="*80)
