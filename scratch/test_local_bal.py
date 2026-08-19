import os
from dotenv import load_dotenv

load_dotenv()

POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS")
POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY")
POLYMARKET_API_SECRET = os.getenv("POLYMARKET_API_SECRET")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE")
POLYMARKET_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY")

print("POLYMARKET_ADDRESS:", POLYMARKET_ADDRESS)
print("POLYMARKET_API_KEY:", POLYMARKET_API_KEY)

from py_clob_client_v2 import ClobClient, ApiCreds
from eth_account import Account

eoa_address = Account.from_key(POLYMARKET_PRIVATE_KEY).address
sig_type = 0
funder_addr = None
if POLYMARKET_ADDRESS and POLYMARKET_ADDRESS.lower() != eoa_address.lower():
    sig_type = 3
    funder_addr = POLYMARKET_ADDRESS

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
    signature_type=sig_type,
    funder=funder_addr
)

from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType

params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
resp = clob_client.get_balance_allowance(params)
print("RAW RESP:", resp)
raw_bal = float(resp.get("balance", 0))
bal = raw_bal / 1_000_000.0
print(f"CALCULATED BALANCE: ${bal:.4f}")
