import os
import json
import requests
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("d:/Desktop/antigravity/POLYBOT/polybot/scalper_bailout_deploy/.env")

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2 import ApiCreds
from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType

WALLET = os.getenv("POLYMARKET_ADDRESS", "")
KEY    = os.getenv("POLYMARKET_PRIVATE_KEY", "")
API_KEY= os.getenv("POLYMARKET_API_KEY", "")
SECRET = os.getenv("POLYMARKET_API_SECRET", "")
PASS   = os.getenv("POLYMARKET_API_PASSPHRASE", "")

print("="*90)
print("🔍 RAW VERBATIM SERVER RESPONSES DIRECTLY FROM POLYMARKET CLOB & POLYGON RPC")
print("="*90)
print(f"Configured Wallet Address: {WALLET}")
print("-" * 90)

# 1. Direct Polymarket CLOB Balance Query
creds = ApiCreds(api_key=API_KEY, api_secret=SECRET, api_passphrase=PASS)
client = ClobClient(
    host="https://clob.polymarket.com",
    key=KEY,
    chain_id=137,
    creds=creds,
    signature_type=3,
    funder=WALLET
)

print("\n1. RAW CLOB API RESPONSE (/balance-allowance?asset_type=COLLATERAL):")
raw_clob = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
print(json.dumps(raw_clob, indent=2))

# 2. Polygon RPC Native Contract Balance Query
RPC_URL = "https://polygon-bor-rpc.publicnode.com"
# Native USDC on Polygon: 0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359
# Bridged USDC.e on Polygon: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
# Function selector: balanceOf(address) = 0x70a08231 + padded address
addr_padded = WALLET[2:].lower().zfill(64)
data_call = "0x70a08231" + addr_padded

print("\n2. RAW POLYGON BLOCKCHAIN RPC RESPONSE (USDC.e Contract 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174):")
payload_rpc_usdce = {
    "jsonrpc": "2.0",
    "method": "eth_call",
    "params": [{"to": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", "data": data_call}, "latest"],
    "id": 1
}
res_rpc_usdce = requests.post(RPC_URL, json=payload_rpc_usdce, timeout=5).json()
print(json.dumps(res_rpc_usdce, indent=2))
hex_bal_usdce = res_rpc_usdce.get("result", "0x0")
raw_usdce = int(hex_bal_usdce, 16) / 1_000_000
print(f"-> Parsed USDC.e on-chain: ${raw_usdce:.6f}")

print("\n3. RAW POLYGON BLOCKCHAIN RPC RESPONSE (Native USDC Contract 0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359):")
payload_rpc_usdc = {
    "jsonrpc": "2.0",
    "method": "eth_call",
    "params": [{"to": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", "data": data_call}, "latest"],
    "id": 2
}
res_rpc_usdc = requests.post(RPC_URL, json=payload_rpc_usdc, timeout=5).json()
print(json.dumps(res_rpc_usdc, indent=2))
hex_bal_usdc = res_rpc_usdc.get("result", "0x0")
raw_usdc = int(hex_bal_usdc, 16) / 1_000_000
print(f"-> Parsed Native USDC on-chain: ${raw_usdc:.6f}")

# 4. Polymarket Data API Positions Query
print("\n4. RAW POLYMARKET DATA API RESPONSE (/positions?user=WALLET):")
r_pos = requests.get(f"https://data-api.polymarket.com/positions?user={WALLET}", timeout=5).json()
print(json.dumps(r_pos, indent=2))

print("="*90)
