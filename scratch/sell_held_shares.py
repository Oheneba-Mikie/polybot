import os
import time
import requests
import json
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("d:/Desktop/antigravity/POLYBOT/polybot/scalper_bailout_deploy/.env")

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2 import MarketOrderArgsV2, OrderType, ApiCreds

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

now = time.time()
cur_w_s = int(now // 300) * 300
slug = f"btc-updown-5m-{cur_w_s}"
r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=5).json()
mkt = r[0]["markets"][0]
clob_tokens = json.loads(mkt.get("clobTokenIds", "[]"))
up_id = clob_tokens[0]

print("="*80)
print("🚨 EXECUTING IMMEDIATE SELL OF HELD SHARES BACK TO CASH:")
print("="*80)

# Check token balance
from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=up_id))
token_bal = float(resp.get("balance", 0)) / 1_000_000
print(f"Held on-chain shares of UP: {token_bal:.4f} shares")

if token_bal >= 0.1:
    sh_to_sell = round(token_bal, 2)
    print(f"Selling {sh_to_sell:.2f} shares at market...")
    res = client.create_and_post_market_order(
        MarketOrderArgsV2(token_id=up_id, amount=sh_to_sell, price=0.01, side="SELL", order_type=OrderType.FAK),
        order_type=OrderType.FAK
    )
    print("✅ SOLD ON-CHAIN! Response:", res)
else:
    print("Zero shares held.")

# Check collateral balance
bal_col = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
cash_bal = float(bal_col.get("balance", 0)) / 1_000_000
print(f"\n💵 Current Wallet Cash Balance: ${cash_bal:.4f} USDC")
print("="*80)
