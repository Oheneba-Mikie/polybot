import os, requests, json, sys, datetime
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv('step_trend_scalper_deploy/.env')

addr = os.getenv('POLYMARKET_ADDRESS')
print('='*90)
print(f'📊 COMPREHENSIVE ON-CHAIN FINANCIAL AUDIT FOR: {addr}')
print('='*90)

# 1. Fetch CLOB Collateral Cash Balance
cash_bal = 0.0
try:
    from py_clob_client_v2 import ClobClient, ApiCreds
    from eth_account import Account
    
    priv_key = os.getenv('POLYMARKET_PRIVATE_KEY')
    api_key = os.getenv('POLYMARKET_API_KEY')
    api_secret = os.getenv('POLYMARKET_API_SECRET')
    api_passphrase = os.getenv('POLYMARKET_API_PASSPHRASE')
    
    eoa = Account.from_key(priv_key).address
    sig = 3 if addr and addr.lower() != eoa.lower() else 0
    creds = ApiCreds(api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase)
    client = ClobClient(host='https://clob.polymarket.com', chain_id=137, key=priv_key, creds=creds, signature_type=sig, funder=addr)
    
    from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
    resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
    cash_bal = float(resp.get('balance', 0)) / 1e6
except Exception as e:
    print(f'Error getting CLOB balance: {e}')

print(f'💰 CURRENT AVAILABLE LIQUID CASH:  USDC')
print('-'*90)

# 2. Fetch all trades placed today (since 00:00 UTC Sept 10)
trades = requests.get(f'https://data-api.polymarket.com/trades?user={addr}&limit=150', timeout=10).json()

# Group trades by market question / slug
market_groups = {}

for t in trades:
    title = t.get('title', 'Unknown Market')
    ts = t.get('timestamp')
    t_dt = datetime.datetime.fromtimestamp(ts) if ts else None
    
    # Filter for today's trades (Sept 10)
    if t_dt and t_dt.date() == datetime.date(2026, 9, 10):
        if title not in market_groups:
            market_groups[title] = []
        market_groups[title].append(t)

print(f'Found {len(market_groups)} Distinct Markets Traded Today on Sept 10:\n')

grand_total_spent = 0.0
grand_total_returned = 0.0

for title, m_trades in market_groups.items():
    print(f'📁 MARKET: {title}')
    
    total_spent = 0.0
    total_returned = 0.0
    shares_held = {}
    
    for t in sorted(m_trades, key=lambda x: x.get('timestamp', 0)):
        side = t.get('side', '').upper()
        size = float(t.get('size', 0))
        price = float(t.get('price', 0))
        cost = size * price
        outcome = t.get('outcome', 'Token')
        ts = t.get('timestamp')
        t_str = datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S') if ts else 'N/A'
        
        if side == 'BUY':
            total_spent += cost
            shares_held[outcome] = shares_held.get(outcome, 0.0) + size
            print(f'   • [{t_str}] BUY  {size:6.2f} {outcome:<4} @  (-)')
        elif side == 'SELL':
            total_returned += cost
            shares_held[outcome] = shares_held.get(outcome, 0.0) - size
            print(f'   • [{t_str}] SELL {size:6.2f} {outcome:<4} @  (+)')
            
    net_window_pnl = total_returned - total_spent
    grand_total_spent += total_spent
    grand_total_returned += total_returned
    
    print(f'   -> Total In:  | Total Out:  | Window P&L: {net_window_pnl:>+.4f} USD')
    for out, rem_sz in shares_held.items():
        if abs(rem_sz) > 0.01:
            print(f'   -> Unsold Shares Held Into Expiry: {rem_sz:.2f} shares of {out}')
    print('-'*90)

print(f'📊 TODAY\'S SUMMARY (Sept 10):')
print(f'• Total Capital Deployed across all trades: ')
print(f'• Total Revenue from Scalp Sells:          ')
print(f'• Net Realized Trading P&L:                {grand_total_returned - grand_total_spent:>+.2f} USD')
print(f'• Final Wallet Balance:                     USDC')
print('='*90)
