import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
WALLET = "0x89B489569F1B2384ee02E958444aF6091219bfe9"

print("="*80)
print("🔍 CHECKING RECENT TRADES AND POSITION STATUS:")
print("="*80)

try:
    r = requests.get(f"{DATA_HOST}/trades?maker={WALLET}&limit=10", timeout=5).json()
    if not r:
        r = requests.get(f"{DATA_HOST}/trades?taker={WALLET}&limit=10", timeout=5).json()
    
    print(f"Fetched {len(r)} trades:")
    for t in r:
        ts = t.get("timestamp", 0)
        side = t.get("side", "")
        size = float(t.get("size", 0))
        price = float(t.get("price", 0))
        outcome = t.get("outcome", "")
        market = t.get("market", "")[:20]
        print(f"[{ts}] {side:<4} | {outcome:<4} | {size:.2f} shares @ ${price:.4f} | Market: {market}")
except Exception as e:
    print(f"Error: {e}")

# Check on-chain token balance
try:
    from py_clob_client_v2.client import ClobClient
    import os
    from dotenv import load_dotenv
    load_dotenv("d:/Desktop/antigravity/POLYBOT/polybot/scalper_bailout_deploy/.env")
    
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=os.getenv("POLYMARKET_PRIVATE_KEY"),
        chain_id=137,
        signature_type=2,
        funder=WALLET
    )
    client.set_api_creds(client.create_or_derive_api_creds())
    
    # Get positions / balance
    bal = client.get_balance()
    print("\nCollateral Balance:", bal)
except Exception as e:
    print(f"CLOB Check Error: {e}")

print("="*80)
