import os
import sys
import json
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

POLYMARKET_ADDRESS         = os.getenv("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY         = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET      = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE  = os.getenv("POLYMARKET_API_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY     = os.getenv("POLYMARKET_PRIVATE_KEY", "")

from py_clob_client_v2 import ClobClient, ApiCreds, OpenOrderParams

creds = ApiCreds(
    api_key=POLYMARKET_API_KEY,
    api_secret=POLYMARKET_API_SECRET,
    api_passphrase=POLYMARKET_API_PASSPHRASE
)
client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=POLYMARKET_PRIVATE_KEY,
    creds=creds,
    signature_type=3,
    funder=POLYMARKET_ADDRESS
)

print("="*95)
print("🔍 CHECKING OPEN ORDERS & CLOB ORDER STATUS FOR WALLET")
print("="*95)

try:
    orders = client.get_open_orders(OpenOrderParams(market=None))
    print(f"Active Open Orders on CLOB: {len(orders)}")
    for o in orders:
        print(f"  • Order ID: {o.get('id')} | Price: ${o.get('price')} | Size: {o.get('size')} | Side: {o.get('side')} | Status: {o.get('status')}")
except Exception as e:
    print("Open Orders Error:", e)

print("="*95)
