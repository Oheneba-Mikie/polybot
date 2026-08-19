import os
from dotenv import load_dotenv

load_dotenv()

POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS")
POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY")
POLYMARKET_API_SECRET = os.getenv("POLYMARKET_API_SECRET")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE")
POLYMARKET_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY")

from py_clob_client_v2 import ClobClient, ApiCreds

creds = ApiCreds(
    api_key=POLYMARKET_API_KEY,
    api_secret=POLYMARKET_API_SECRET,
    api_passphrase=POLYMARKET_API_PASSPHRASE
)
clob_client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=POLYMARKET_PRIVATE_KEY,
    creds=creds,
    signature_type=3,
    funder=POLYMARKET_ADDRESS
)

try:
    orders = clob_client.get_open_orders()
    print("OPEN ORDERS ON POLYMARKET CLOB:")
    import json
    print(json.dumps(orders, indent=2))
except Exception as e:
    print("Error querying open orders:", e)
