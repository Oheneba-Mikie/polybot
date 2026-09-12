import os, requests, json, sys, datetime
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv('step_trend_scalper_deploy/.env')

addr = os.getenv('POLYMARKET_ADDRESS')
api_key = os.getenv('POLYMARKET_API_KEY')
api_secret = os.getenv('POLYMARKET_API_SECRET')
api_passphrase = os.getenv('POLYMARKET_API_PASSPHRASE')
priv_key = os.getenv('POLYMARKET_PRIVATE_KEY')

print('='*80)
print(f'🔍 FULL WALLET AUDIT FOR ADDRESS: {addr}')
print('='*80)

# 1. Query CLOB Balance & Allowance
try:
    from py_clob_client_v2 import ClobClient, ApiCreds
    from eth_account import Account
    
    eoa = Account.from_key(priv_key).address
    sig = 3 if addr and addr.lower() != eoa.lower() else 0
    creds = ApiCreds(api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase)
    client = ClobClient(host='https://clob.polymarket.com', chain_id=137, key=priv_key, creds=creds, signature_type=sig, funder=addr)
    
    from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
    bal_collateral = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
    cash_bal = float(bal_collateral.get('balance', 0)) / 1e6
    print(f'💵 Free Cash (USDC Collateral in CLOB):  USDC')
except Exception as e:
    print(f'Error querying CLOB balance: {e}')

# 2. Query Open/Unredeemed Positions via Data API
try:
    pos_res = requests.get(f'https://data-api.polymarket.com/positions?user={addr}&sizeThreshold=0.01', timeout=10).json()
    print(f'\n📦 Open / Unredeemed Positions Found: {len(pos_res)}')
    total_unredeemed_value = 0.0
    for p in pos_res:
        title = p.get('title', 'Unknown')
        outcome = p.get('outcome', '')
        size = float(p.get('size', 0))
        cur_val = float(p.get('currentValue', 0))
        redeemable = p.get('redeemable', False)
        total_unredeemed_value += cur_val
        print(f'  • {title} | Outcome: {outcome} | Size: {size:.2f} shares | Value:  | Redeemable: {redeemable}')
    print(f'💰 Total Value in Positions / Unclaimed: ')
except Exception as e:
    print(f'Error querying positions: {e}')

# 3. Query All Trades Placed Today
try:
    trades_res = requests.get(f'https://data-api.polymarket.com/trades?taker_address={addr}&limit=30', timeout=10).json()
    print(f'\n📜 Last {len(trades_res)} Recent Trades:')
    for t in trades_res[:15]:
        side = t.get('side')
        size = t.get('size')
        price = t.get('price')
        title = t.get('title', '')
        ts = t.get('timestamp')
        import datetime
        t_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else 'N/A'
        val = float(size) * float(price) if size and price else 0
        print(f'  [{t_str}] {side:<4} | Size: {size:<6} @  () | Market: {title}')
except Exception as e:
    print(f'Error querying trades: {e}')

print('='*80)
