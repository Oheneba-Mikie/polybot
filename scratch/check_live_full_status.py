import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("scalper_bailout_deploy/.env")

CLOB_HOST = "https://clob.polymarket.com"
DATA_HOST = "https://data-api.polymarket.com"

POLYMARKET_ADDRESS        = os.getenv("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY        = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET     = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY    = os.getenv("POLYMARKET_PRIVATE_KEY", "")

print("="*100)
print("🔍 COMPLETE LIVE WALLET, CLOB, POSITION & RECENT TRADES AUDIT")
print("="*100)

print(f"Target Wallet Address: {POLYMARKET_ADDRESS}")

# 1. Check Live CLOB Balance & Allowance
try:
    from scalper_bailout_deploy.py_clob_client_v2 import ClobClient, ApiCreds
    from scalper_bailout_deploy.py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
    
    creds = ApiCreds(
        api_key=POLYMARKET_API_KEY,
        api_secret=POLYMARKET_API_SECRET,
        api_passphrase=POLYMARKET_API_PASSPHRASE
    )
    client = ClobClient(
        host=CLOB_HOST,
        chain_id=137,
        key=POLYMARKET_PRIVATE_KEY,
        creds=creds,
        signature_type=3,
        funder=POLYMARKET_ADDRESS
    )
    
    resp_bal = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
    raw_bal = float(resp_bal.get("balance", 0)) / 1_000_000
    raw_allowance = float(resp_bal.get("allowance", 0)) / 1_000_000
    print(f"\n💵 CLOB Collateral Balance : ${raw_bal:.6f} USDC (Raw units: {resp_bal.get('balance')})")
    print(f"🔑 CLOB Collateral Allowance: ${raw_allowance:.6f} USDC (Raw units: {resp_bal.get('allowance')})")
except Exception as e:
    print(f"Error checking CLOB balance: {e}")

# 2. Check Open Orders on CLOB
try:
    open_orders = client.get_orders()
    print(f"\n📋 Currently Open Orders on Book: {len(open_orders)}")
    for o in open_orders:
        print(f"  • Order ID: {o.get('id')} | Side: {o.get('side')} | Price: {o.get('price')} | Size: {o.get('original_size')}")
except Exception as e:
    print(f"Error checking open orders: {e}")

# 3. Check Current Open Positions (Are any shares currently held?)
try:
    r_pos = requests.get(f"{DATA_HOST}/positions?user={POLYMARKET_ADDRESS}&sizeThreshold=0.1", timeout=10).json()
    print(f"\n📊 Current Open Token Positions: {len(r_pos)}")
    for p in r_pos:
        print(f"  • Market: {p.get('title', 'Unknown')[:40]} | Outcome: {p.get('outcome')} | Shares Held: {p.get('size')} | Current Value: ${float(p.get('currentValue', 0)):.2f}")
except Exception as e:
    print(f"Error checking open positions: {e}")

# 4. Check Latest 10 On-Chain Activities / Trades
try:
    r_act = requests.get(f"{DATA_HOST}/activity?user={POLYMARKET_ADDRESS}&limit=10", timeout=10).json()
    print(f"\n📜 Last 10 Trade Transactions on Polymarket:")
    print(f"{'#':<3} | {'TIMESTAMP (UTC)':<19} | {'TYPE':<6} | {'SIDE':<5} | {'PRICE':<6} | {'SHARES':<10} | {'USDC AMOUNT':<12} | {'TITLE'}")
    print("-"*100)
    for i, a in enumerate(r_act):
        ts = a.get("timestamp", 0)
        dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        a_type = a.get("type", "")
        side = a.get("side", "")
        px = float(a.get("price") or 0)
        sz = float(a.get("size") or 0)
        usdc = float(a.get("usdcSize") or (px * sz))
        title = a.get("title", "")[:35]
        print(f"{i+1:<3} | {dt_str:<19} | {a_type:<6} | {side:<5} | ${px:<5.2f} | {sz:<10.2f} | ${usdc:<11.2f} | {title}")
except Exception as e:
    print(f"Error checking recent activity: {e}")

print("="*100)
