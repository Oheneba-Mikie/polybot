import os, requests, json, sys, datetime
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv('step_trend_scalper_deploy/.env')

addr = os.getenv('POLYMARKET_ADDRESS')
print('='*80)
print(f'🔍 THOROUGH STEP-BY-STEP AUDIT FOR WALLET: {addr}')
print('='*80)

# 1. Fetch user trades from Polymarket Data API
trades = requests.get(f'https://data-api.polymarket.com/trades?user={addr}&limit=100', timeout=10).json()
print(f'Total Recent Trades in Account: {len(trades)}')
print('-'*80)

total_bought = 0.0
total_sold = 0.0

for t in trades[:30]:
    side = t.get('side', '')
    size = float(t.get('size', 0))
    price = float(t.get('price', 0))
    dollar_val = size * price
    title = t.get('title', 'Unknown')
    outcome = t.get('outcome', '')
    ts = t.get('timestamp')
    t_str = datetime.datetime.fromtimestamp(ts).strftime('%m/%d %H:%M:%S') if ts else 'N/A'
    
    if side.upper() == 'BUY':
        total_bought += dollar_val
    elif side.upper() == 'SELL':
        total_sold += dollar_val
        
    print(f'[{t_str}] {side:<4} | {size:6.2f} shares of {outcome:<4} @  () | {title}')

print('-'*80)

# 2. Check Open Positions
positions = requests.get(f'https://data-api.polymarket.com/positions?user={addr}', timeout=10).json()
print(f'\n📦 Open Positions / Unredeemed Balance:')
for p in positions:
    sz = float(p.get('size', 0))
    if sz > 0.01:
        val = float(p.get('currentValue', 0))
        redeem = p.get('redeemable', False)
        title = p.get('title', '')
        outcome = p.get('outcome', '')
        print(f'  • {title} ({outcome}): {sz:.2f} shares | Current Value:  | Redeemable: {redeem}')

print('='*80)
