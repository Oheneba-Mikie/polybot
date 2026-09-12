import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

WALLET = "0x89B489569F1B2384ee02E958444aF6091219bfe9"

print("="*95)
print(f"🔍 COMPLETE ON-CHAIN TRANSACTION & TRANSFER AUDIT FOR: {WALLET}")
print("="*95)

# Query PolygonScan or public explorer for ERC20 USDC token transfers
url = f"https://api.polygonscan.com/api?module=account&action=tokentx&address={WALLET}&startblock=0&endblock=99999999&sort=desc"

try:
    r = requests.get(url, timeout=5).json()
    status = r.get("status")
    result = r.get("result", [])
    
    if isinstance(result, list) and len(result) > 0:
        print(f"Found {len(result)} on-chain ERC20 transactions:")
        print("-" * 95)
        for tx in result[:15]:
            ts = int(tx.get("timeStamp", 0))
            dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            from_addr = tx.get("from", "")
            to_addr = tx.get("to", "")
            val = float(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 6)))
            symbol = tx.get("tokenSymbol", "")
            tx_hash = tx.get("hash", "")
            
            direction = "INCOMING (+)" if to_addr.lower() == WALLET.lower() else "OUTGOING (-)"
            print(f"[{dt}] {direction:<12} | {val:>10.4f} {symbol:<6} | From: {from_addr[:10]}... -> To: {to_addr[:10]}... | Tx: {tx_hash[:16]}...")
    else:
        print("Polygonscan returned:", result)
except Exception as e:
    print(f"Error querying Polygonscan: {e}")

# Also query Polymarket CLOB trade history directly
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

print("\n" + "="*95)
print("📊 CLOB EXACT CURRENT BALANCE & ALLOWANCES:")
print("="*95)
bal_col = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
print(json.dumps(bal_col, indent=2))
print("="*95)
