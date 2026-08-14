import requests
import datetime

ADDRESS = '0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8'
r = requests.get('https://data-api.polymarket.com/activity', params={'user': ADDRESS, 'limit': 50}, timeout=10)
acts = r.json()

print('=' * 80)
print('  POLYMARKET TRADE HISTORY')
print('=' * 80)

total_spent = 0.0
total_received = 0.0

for a in reversed(acts):
    t_type = a.get('type')
    if t_type not in ('TRADE', 'REDEEM'):
        continue
    ts = a.get('timestamp', 0)
    dt = datetime.datetime.fromtimestamp(ts, datetime.UTC).strftime('%H:%M UTC')
    title = a.get('title', '')[:50]
    outcome = a.get('outcome', '')
    size = float(a.get('usdcSize', 0))
    side = a.get('side', '')
    shares = float(a.get('size', 0))
    price = float(a.get('price', 0)) if a.get('price') else 0

    if t_type == 'TRADE' and side == 'BUY':
        total_spent += size
        print(f'  BUY    {dt}  {outcome:<5}  price=${price:.2f}  {shares:.2f} shares  COST=${size:.2f}  {title}')
    elif t_type == 'REDEEM':
        total_received += size
        print(f'  REDEEM {dt}  {outcome:<5}                  {shares:.2f} shares  RECV=${size:.2f}  {title}')
    elif t_type == 'TRADE' and side == 'SELL':
        total_received += size
        print(f'  SELL   {dt}  {outcome:<5}  price=${price:.2f}  {shares:.2f} shares  RECV=${size:.2f}  {title}')

print()
print('=' * 80)
print(f'  TOTAL SPENT   : {total_spent:.4f}')
print(f'  TOTAL RECEIVED: {total_received:.4f}')
print(f'  NET P&L       : {total_received - total_spent:+.4f}')
print('=' * 80)
