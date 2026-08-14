import json
import datetime

with open('scratch/analyzed_trades.json', encoding='utf-8') as f:
    trades = json.load(f)

scalper_trades = [t for t in trades if t.get('price', 0) >= 0.90]

print(f"Total Scalper ($0.90+) trades: {len(scalper_trades)}")

wins = [t for t in scalper_trades if t.get('is_win') is True]
losses = [t for t in scalper_trades if t.get('is_win') is False]

print(f"Wins: {len(wins)}, Losses: {len(losses)}")

# Timestamps min/max
ts_list = [t['timestamp'] for t in scalper_trades]
min_dt = datetime.datetime.fromtimestamp(min(ts_list), datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
max_dt = datetime.datetime.fromtimestamp(max(ts_list), datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')

print(f"Earliest Scalper Trade: {min_dt}")
print(f"Latest Scalper Trade  : {max_dt}")

# Group by day
by_day = {}
for t in scalper_trades:
    day = datetime.datetime.fromtimestamp(t['timestamp'], datetime.UTC).strftime('%Y-%m-%d')
    by_day[day] = by_day.get(day, 0) + 1

print("\nScalper Trades by Date:")
for d, count in sorted(by_day.items()):
    print(f"  - {d}: {count} trades")

print("\nLosses in Scalper ($0.90+):")
for idx, l in enumerate(losses, 1):
    dt = l['datetime']
    title = l['title']
    price = l['price']
    bought = l['outcome_bought']
    winner = l['winning_outcome']
    size = l['usdc_size']
    print(f"  {idx}. {dt} | Bought {bought} @ ${price:.4f} (${size:.2f}) | Winner: {winner} | Market: {title}")
