import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

addr = "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"

print("="*95)
print(f"📜 COMPLETE FINANCIAL LEDGER & BALANCE AUDIT FOR WALLET: {addr}")
print("="*95)

# 1. Pull full activity history from Polymarket
r_act = requests.get(f"https://data-api.polymarket.com/activity?user={addr}&limit=50").json()
print(f"Total Activity Records: {len(r_act)}\n")

# Print chronologically (oldest to newest)
for idx, a in enumerate(reversed(r_act), 1):
    dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(a.get("timestamp", 0)))
    typ = a.get("type", "N/A")
    side = a.get("side", "")
    usdc = a.get("usdcSize", a.get("size", 0))
    sh = a.get("size", 0)
    title = a.get("title", "N/A")
    outcome = a.get("outcome", "")
    print(f"  [{idx:02d}] {dt} | Type: {typ:<7} | Side: {side:<4} | Amount: ${float(usdc):<6.2f} | Shares: {float(sh):<6.3f} {outcome:<4} | Market: {title}")

# 2. Query current live balance
from dotenv import load_dotenv
import os
load_dotenv("scalper_bailout_deploy/.env")
from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import ApiCreds, BalanceAllowanceParams, AssetType

key = os.getenv("POLYMARKET_PRIVATE_KEY")
creds = ApiCreds(
    api_key=os.getenv("POLYMARKET_API_KEY"),
    api_secret=os.getenv("POLYMARKET_API_SECRET"),
    api_passphrase=os.getenv("POLYMARKET_API_PASSPHRASE")
)
client = ClobClient(host="https://clob.polymarket.com", chain_id=137, key=key, creds=creds, signature_type=3, funder=addr)
resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=3))
raw_b = float(resp.get("balance", 0)) / 1_000_000

print("\n" + "="*95)
print(f"💰 CURRENT LIVE CASH BALANCE: ${raw_b:.4f} USDC")
print("="*95)
