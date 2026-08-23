import os
from dotenv import load_dotenv
from py_clob_client_v2 import ClobClient, ApiCreds, OrderType, MarketOrderArgsV2
from py_clob_client_v2.clob_types import OrderArgs

load_dotenv("scalper_bailout_deploy/.env")

creds = ApiCreds(
    api_key=os.getenv("POLYMARKET_API_KEY"),
    api_secret=os.getenv("POLYMARKET_API_SECRET"),
    api_passphrase=os.getenv("POLYMARKET_API_PASSPHRASE")
)
client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=os.getenv("POLYMARKET_PRIVATE_KEY"),
    creds=creds,
    signature_type=3,
    funder=os.getenv("POLYMARKET_ADDRESS")
)

# Test creating a signed order of 1.5 shares to verify if CLOB validation accepts it
try:
    # We can check min order size from client or CLOB endpoint
    min_sz = client.get_min_order_size()
    print("CLOB Minimum Order Size:", min_sz)
except Exception as e:
    print("Min size query:", e)

# Also check historical trades by this user: what was the lowest share size ever traded?
import requests
r_trades = requests.get(f"https://data-api.polymarket.com/trades?user={os.getenv('POLYMARKET_ADDRESS')}&limit=50").json()
sizes = [float(t.get("size", 0)) for t in r_trades]
if sizes:
    print(f"Smallest share trade in your history: {min(sizes):.4f} shares")
    print(f"All trade share sizes: {sorted(sizes)[:10]}")
