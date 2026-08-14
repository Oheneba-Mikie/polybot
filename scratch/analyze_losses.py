import json
import os
import requests
import datetime

ADDRESS = '0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8'

# 1. Fetch trades
url = f'https://data-api.polymarket.com/activity?user={ADDRESS}&limit=500'
r = requests.get(url, timeout=15)
activities = r.json()

trades = [a for a in activities if a.get('type') == 'TRADE' and a.get('side') == 'BUY']
print(f"Total BUY trades fetched: {len(trades)}")

market_cache = {}

def get_market(condition_id, slug):
    if slug and slug in market_cache:
        return market_cache[slug]
    try:
        if slug:
            res = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=10)
            if res.status_code == 200 and res.json():
                mkt = res.json()[0]['markets'][0]
                market_cache[slug] = mkt
                return mkt
        res = requests.get(f"https://gamma-api.polymarket.com/markets?condition_id={condition_id}", timeout=10)
        if res.status_code == 200 and res.json():
            mkt = res.json()[0]
            market_cache[condition_id] = mkt
            return mkt
    except Exception as e:
        print(f"Error fetching market {slug}: {e}")
    return {}

analyzed = []
for t in trades:
    ts = t.get('timestamp', 0)
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
    title = t.get('title', '')
    outcome_bought = str(t.get('outcome', '')).strip().upper()
    price = float(t.get('price', 0))
    usdc_size = float(t.get('usdcSize', 0))
    condition_id = t.get('conditionId')
    slug = t.get('slug')

    mkt = get_market(condition_id, slug)
    
    # Parse outcome prices
    op_raw = mkt.get('outcomePrices') or '[]'
    out_raw = mkt.get('outcomes') or '[]'
    try:
        op = [float(p) for p in json.loads(op_raw)]
        outcomes = [str(o).upper() for o in json.loads(out_raw)]
    except:
        op = []
        outcomes = []

    winning_outcome = None
    if len(op) >= 2 and len(outcomes) >= 2:
        if op[0] >= 0.90:
            winning_outcome = outcomes[0]
        elif op[1] >= 0.90:
            winning_outcome = outcomes[1]

    # Map YES/NO to UP/DOWN if needed
    normal_bought = outcome_bought
    if outcome_bought == 'YES': normal_bought = 'UP'
    elif outcome_bought == 'NO': normal_bought = 'DOWN'

    normal_winner = winning_outcome
    if winning_outcome == 'YES': normal_winner = 'UP'
    elif winning_outcome == 'NO': normal_winner = 'DOWN'

    is_win = None
    if normal_winner:
        is_win = (normal_bought == normal_winner)

    analyzed.append({
        'timestamp': ts,
        'datetime': dt_str,
        'title': title,
        'slug': slug,
        'outcome_bought': outcome_bought,
        'normal_bought': normal_bought,
        'winning_outcome': winning_outcome,
        'normal_winner': normal_winner,
        'price': price,
        'usdc_size': usdc_size,
        'is_win': is_win,
        'question': mkt.get('question', title),
        'description': mkt.get('description', '')
    })

# Write to json
with open('scratch/analyzed_results.json', 'w') as f:
    json.dump(analyzed, f, indent=2)

losses = [a for a in analyzed if a['is_win'] is False]
wins = [a for a in analyzed if a['is_win'] is True]
unresolved = [a for a in analyzed if a['is_win'] is None]

print("\n" + "="*80)
print(f"  ANALYSIS SUMMARY: Total: {len(analyzed)} | Wins: {len(wins)} | Losses: {len(losses)} | Unresolved: {len(unresolved)}")
print("="*80)

print("\n--- ALL LOST TRADES ---")
for idx, l in enumerate(losses, 1):
    print(f"\n[{idx}] {l['datetime']} | {l['title']}")
    print(f"    Bought: {l['outcome_bought']} @ ${l['price']:.4f}  (Cost: ${l['usdc_size']:.2f})")
    print(f"    Winning Outcome: {l['winning_outcome']} (Normal Winner: {l['normal_winner']})")
    print(f"    Slug: {l['slug']}")
