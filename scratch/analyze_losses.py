import requests
import json
import datetime

ADDRESS = '0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8'

def get_activities():
    url = f'https://data-api.polymarket.com/activity?user={ADDRESS}&limit=200'
    r = requests.get(url, timeout=15)
    return r.json()

def get_closed_positions():
    url = f'https://data-api.polymarket.com/closed-positions?user={ADDRESS}&limit=100'
    try:
        r = requests.get(url, timeout=15)
        return r.json()
    except Exception as e:
        return []

acts = get_activities()
print(f"Fetched {len(acts)} activities")

trades = []
for a in acts:
    t_type = a.get('type')
    ts = a.get('timestamp', 0)
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    title = a.get('title', '')
    condition_id = a.get('conditionId', '')
    outcome = a.get('outcome', '')
    size = float(a.get('usdcSize', 0) or 0)
    side = a.get('side', '')
    shares = float(a.get('size', 0) or 0)
    price = float(a.get('price', 0) or 0)
    trades.append({
        'type': t_type,
        'timestamp': ts,
        'datetime': dt_str,
        'title': title,
        'condition_id': condition_id,
        'outcome': outcome,
        'size': size,
        'side': side,
        'shares': shares,
        'price': price,
        'raw': a
    })

trades.sort(key=lambda x: x['timestamp'])

print("\n--- ALL RECENT ACTIVITIES (CHRONOLOGICAL) ---")
for t in trades[-60:]:
    print(f"[{t['datetime']}] {t['type']} | Side: {t['side']} | {t['outcome']} | Px: {t['price']:.3f} | Shares: {t['shares']:.2f} | USDC: {t['size']:.2f} | {t['title'][:60]}")

with open('scratch/recent_activities.json', 'w') as f:
    json.dump(acts, f, indent=2)
