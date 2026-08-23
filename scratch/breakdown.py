import requests
import json
import datetime
from collections import defaultdict

ADDRESS = '0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8'

all_acts = []
offset = 0
while True:
    url = f'https://data-api.polymarket.com/activity?user={ADDRESS}&limit=100&offset={offset}'
    try:
        r = requests.get(url, timeout=15)
        batch = r.json()
        if not batch:
            break
        all_acts.extend(batch)
        if len(batch) < 100:
            break
        offset += 100
        if offset >= 1000:
            break
    except Exception as e:
        print(f"Error fetching offset {offset}: {e}")
        break

print(f"Total activities retrieved: {len(all_acts)}")

# Group activities by conditionId / market
markets = defaultdict(lambda: {
    'title': '',
    'buys': [],
    'sells': [],
    'redeems': [],
    'total_spent': 0.0,
    'total_redeemed': 0.0,
    'total_sold': 0.0,
    'buy_shares': defaultdict(float),
    'redeem_shares': defaultdict(float),
    'first_ts': None,
    'last_ts': None,
})

for a in all_acts:
    cid = a.get('conditionId') or a.get('market') or a.get('title')
    t_type = a.get('type')
    ts = a.get('timestamp', 0)
    title = a.get('title', '')
    outcome = a.get('outcome', '')
    size = float(a.get('usdcSize', 0) or 0)
    side = a.get('side', '')
    shares = float(a.get('size', 0) or 0)
    price = float(a.get('price', 0) or 0)

    m = markets[cid]
    if not m['title']:
        m['title'] = title
    if m['first_ts'] is None or ts < m['first_ts']:
        m['first_ts'] = ts
    if m['last_ts'] is None or ts > m['last_ts']:
        m['last_ts'] = ts

    if t_type == 'TRADE':
        if side == 'BUY':
            m['buys'].append({'ts': ts, 'outcome': outcome, 'shares': shares, 'price': price, 'size': size})
            m['total_spent'] += size
            m['buy_shares'][outcome] += shares
        elif side == 'SELL':
            m['sells'].append({'ts': ts, 'outcome': outcome, 'shares': shares, 'price': price, 'size': size})
            m['total_sold'] += size
    elif t_type == 'REDEEM':
        m['redeems'].append({'ts': ts, 'outcome': outcome, 'shares': shares, 'size': size})
        m['total_redeemed'] += size
        m['redeem_shares'][outcome] += shares

# Sort markets by first_ts
sorted_markets = sorted(markets.items(), key=lambda x: x[1]['first_ts'] or 0)

print("\n" + "="*100)
print(f"{'DATE (UTC)':<18} | {'MARKET TITLE':<45} | {'SPENT ($)':<9} | {'RECV ($)':<9} | {'P&L ($)':<9} | {'RESULT'}")
print("="*100)

daily_summary = defaultdict(lambda: {'spent': 0.0, 'received': 0.0, 'pnl': 0.0, 'wins': 0, 'losses': 0, 'details': []})

for cid, m in sorted_markets:
    spent = m['total_spent']
    recv = m['total_redeemed'] + m['total_sold']
    pnl = recv - spent
    first_dt = datetime.datetime.fromtimestamp(m['first_ts'], datetime.timezone.utc)
    day_str = first_dt.strftime('%Y-%m-%d')
    dt_str = first_dt.strftime('%Y-%m-%d %H:%M')

    # Determine status
    if spent == 0:
        continue
    
    is_win = (recv > spent)
    is_loss = (recv < spent and abs(recv - spent) > 0.05)
    is_breakeven = abs(recv - spent) <= 0.05

    status = "WIN" if is_win else ("LOSS" if is_loss else "EVEN/OPEN")

    if is_win:
        daily_summary[day_str]['wins'] += 1
    elif is_loss:
        daily_summary[day_str]['losses'] += 1

    daily_summary[day_str]['spent'] += spent
    daily_summary[day_str]['received'] += recv
    daily_summary[day_str]['pnl'] += pnl
    daily_summary[day_str]['details'].append({
        'dt': dt_str,
        'title': m['title'],
        'spent': spent,
        'recv': recv,
        'pnl': pnl,
        'status': status,
        'buys': m['buys'],
        'redeems': m['redeems'],
        'sells': m['sells'],
        'cid': cid
    })

    print(f"{dt_str:<18} | {m['title'][:45]:<45} | ${spent:8.2f} | ${recv:8.2f} | {pnl:+8.2f} | {status}")

print("\n" + "="*100)
print("DAILY SUMMARY:")
print("="*100)
for day, data in sorted(daily_summary.items()):
    print(f"Date: {day} | Trades: {len(data['details'])} | Wins: {data['wins']} | Losses: {data['losses']} | Spent: ${data['spent']:.2f} | Recv: ${data['received']:.2f} | Net P&L: {data['pnl']:+.2f}")

with open('scratch/daily_breakdown.json', 'w') as f:
    json.dump(daily_summary, f, indent=2)
