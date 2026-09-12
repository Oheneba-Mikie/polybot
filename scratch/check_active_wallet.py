import os
import json
import datetime
import requests
from dotenv import load_dotenv

env_path = 'd:/Desktop/antigravity/POLYBOT/polybot/step_trend_scalper_deploy/.env'
load_dotenv(env_path)

pk = os.getenv('POLYMARKET_PRIVATE_KEY')
api_key = os.getenv('POLYMARKET_API_KEY')
api_secret = os.getenv('POLYMARKET_API_SECRET')
api_passphrase = os.getenv('POLYMARKET_API_PASSPHRASE')
funder = os.getenv('POLYMARKET_ADDRESS')

print("Funder Address:", funder)

# 1. Fetch live balance from CLOB API
from py_clob_client_v2 import ClobClient, ApiCreds
from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
from eth_account import Account

eoa_address = Account.from_key(pk).address
sig_type = 3 if funder and funder.lower() != eoa_address.lower() else 0

creds = ApiCreds(api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase)
client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=pk,
    creds=creds,
    signature_type=sig_type,
    funder=funder
)

params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
resp = client.get_balance_allowance(params)
raw_bal = float(resp.get("balance", 0)) / 1_000_000.0
print(f"\n>>> LIVE CLOB USDC BALANCE: ${raw_bal:.4f} USD <<<")
print("Allowances:", resp.get("allowances"))

# 2. Query Data API for all activity for this wallet
print(f"\n=== POLYMARKET DATA API ACTIVITY FOR {funder} ===")
url = f"https://data-api.polymarket.com/activity?user={funder}&limit=30"
r = requests.get(url, timeout=10)
if r.status_code == 200:
    acts = r.json()
    print(f"Total recorded activities: {len(acts)}")
    for a in acts:
        ts = a.get('timestamp')
        dt = datetime.datetime.fromtimestamp(int(ts), datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC') if ts else "N/A"
        print(f"[{dt}] Type: {a.get('type'):<6} | Side: {str(a.get('side')):<4} | Size: {float(a.get('size', 0)):<8.2f} | Price: ${float(a.get('price', 0)):<6.4f} | Title: {a.get('title')} | Outcome: {a.get('outcome')}")
else:
    print(f"Data API error {r.status_code}: {r.text}")

# 3. Check open positions
print(f"\n=== OPEN POSITIONS FOR {funder} ===")
url = f"https://data-api.polymarket.com/positions?user={funder}&sizeThreshold=0.01"
r = requests.get(url, timeout=10)
if r.status_code == 200:
    positions = r.json()
    print(f"Open positions count: {len(positions)}")
    for p in positions:
        print(f"Title: {p.get('title')} | Outcome: {p.get('outcome')} | Size: {p.get('size')} | CurVal: ${p.get('currentValue')}")
else:
    print(f"Positions error {r.status_code}")
