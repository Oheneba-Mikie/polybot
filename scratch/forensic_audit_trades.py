import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
POLYMARKET_ADDRESS = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"

r_act = requests.get(f"{DATA_HOST}/activity?user={POLYMARKET_ADDRESS}&limit=50").json()

print("="*90)
print("🔍 ALL TRADES & ACTIVITY ON WALLET SINCE 23:30 UTC:")
print("="*90)

for a in r_act:
    ts = a.get("timestamp", 0)
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    action = a.get("type", "TRADE")
    title = a.get("title", "")
    size = a.get("size", "")
    usdc = a.get("usdcSize", "")
    side = a.get("side", "")
    price = a.get("price", "")
    print(f"[{dt_str}] {action:<6} | {side:<4} {size} shares @ ${price} (${usdc} USDC) | {title}")

print("="*90)

# Check live balance
from py_clob_client_v2 import ClobClient, ApiCreds
import os
from dotenv import load_dotenv

load_dotenv("scalper_bailout_deploy/.env")

creds = ApiCreds(
    api_key=os.getenv("POLYMARKET_API_KEY", ""),
    api_secret=os.getenv("POLYMARKET_API_SECRET", ""),
    api_passphrase=os.getenv("POLYMARKET_API_PASSPHRASE", "")
)
client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=os.getenv("POLYMARKET_PRIVATE_KEY", ""),
    creds=creds,
    signature_type=3,
    funder=os.getenv("POLYMARKET_ADDRESS", "")
)

try:
    b = client.get_balance_allowance({"asset_type": "COLLATERAL"})
    bal = float(b.get("balance", 0)) / 1e6
    print(f"\n💵 LIVE WALLET BALANCE: ${bal:.4f} USDC")
except Exception as e:
    print(f"Balance check error: {e}")
