import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
WALLET = "0x89B489569F1B2384ee02E958444aF6091219bfe9"

print("="*90)
print(f"💼 COMPLETE PORTFOLIO BREAKDOWN FOR WALLET: {WALLET}")
print("="*90)

# 1. Check open positions
r_pos = requests.get(f"{DATA_HOST}/positions?user={WALLET}", timeout=5).json()
total_position_val = 0.0

print(f"Open Positions ({len(r_pos)} active):")
print("-" * 90)
for p in r_pos:
    title = p.get("title", "")
    outcome = p.get("outcome", "")
    size = float(p.get("size", 0))
    val = float(p.get("currentValue", 0))
    avg_px = float(p.get("avgPrice", 0))
    total_position_val += val
    print(f"- {title:<45} | {outcome:<6} | {size:<8.2f} sh | Avg: ${avg_px:.4f} | Value: ${val:.2f}")

# 2. Check on-chain cash balance
from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
import os
from dotenv import load_dotenv

load_dotenv("d:/Desktop/antigravity/POLYBOT/polybot/scalper_bailout_deploy/.env")
client = ClobClient(
    host="https://clob.polymarket.com",
    key=os.getenv("POLYMARKET_PRIVATE_KEY"),
    chain_id=137,
    signature_type=3,
    funder=WALLET
)
bal_col = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
cash_bal = float(bal_col.get("balance", 0)) / 1_000_000

print("-" * 90)
print(f"💵 Available USDC Cash:   ${cash_bal:.4f}")
print(f"📈 Total Position Value:  ${total_position_val:.4f}")
print(f"💰 Total Portfolio Value: ${cash_bal + total_position_val:.4f} USDC")
print("="*90)
