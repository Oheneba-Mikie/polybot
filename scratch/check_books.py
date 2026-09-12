import os
import json
import datetime
import requests
from dotenv import load_dotenv

load_dotenv('d:/Desktop/antigravity/POLYBOT/polybot/.env')

pk = os.getenv('POLYMARKET_PRIVATE_KEY')
api_key = os.getenv('CLOB_API_KEY') or os.getenv('POLYMARKET_API_KEY')
api_secret = os.getenv('CLOB_SECRET') or os.getenv('POLYMARKET_API_SECRET')
api_passphrase = os.getenv('CLOB_PASS_PHRASE') or os.getenv('POLYMARKET_API_PASSPHRASE')
funder = os.getenv('FUNDER_ADDRESS') or os.getenv('POLYMARKET_ADDRESS')

print("Funder address:", funder)

# 1. Fetch balance via py_clob_client_v2
try:
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
    print("=== LIVE CLOB BALANCE (COLLATERAL) ===")
    print(json.dumps(resp, indent=2))
    raw_bal = float(resp.get("balance", 0)) / 1_000_000.0
    print(f"USDC Available: ${raw_bal:.4f} USD")
except Exception as e:
    print("CLOB Balance error:", e)

# 2. Fetch public trades directly from Polymarket Data API for this funder/proxy address
print("\n=== POLYMARKET DATA API ACTIVITY FOR WALLET ===")
for addr in [funder, eoa_address]:
    if not addr: continue
    print(f"\n--- Checking Address: {addr} ---")
    try:
        url = f"https://data-api.polymarket.com/activity?user={addr}&limit=15"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            acts = r.json()
            print(f"Found {len(acts)} activities:")
            for a in acts[:10]:
                ts = a.get('timestamp')
                dt = datetime.datetime.utcfromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S UTC') if ts else "N/A"
                print(f"[{dt}] Type: {a.get('type')} | Side: {a.get('side')} | Size: {a.get('size')} | Price: {a.get('price')} | Title: {a.get('title')} | Outcome: {a.get('outcome')}")
        else:
            print(f"Data API status {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print("Data API error:", e)

# 3. Check live open positions
print("\n=== OPEN POSITIONS ON POLYMARKET ===")
try:
    url = f"https://data-api.polymarket.com/positions?user={funder}&sizeThreshold=0.01"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        positions = r.json()
        print(f"Open positions count: {len(positions)}")
        for p in positions:
            print(f"Title: {p.get('title')} | Outcome: {p.get('outcome')} | Size: {p.get('size')} | CurVal: ${p.get('currentValue')}")
    else:
        print(f"Positions status {r.status_code}")
except Exception as e:
    print("Positions error:", e)
