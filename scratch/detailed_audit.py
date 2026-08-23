import json
import requests
import datetime

with open('scratch/daily_breakdown.json') as f:
    daily = json.load(f)

aug20 = daily['2026-08-20']
print("====================================================================================================")
print("AUGUST 20, 2026 - DOLLAR-BY-DOLLAR BREAKDOWN")
print("====================================================================================================")

total_won = 0.0
total_lost = 0.0

for idx, t in enumerate(aug20['details'], 1):
    status = t['status']
    spent = t['spent']
    recv = t['recv']
    pnl = t['pnl']
    if pnl > 0:
        total_won += pnl
    else:
        total_lost += abs(pnl)
    
    buys_summary = ", ".join([f"{b['shares']:.1f}sh @ {b['price']:.3f} ({b['outcome']})" for b in t['buys']])
    print(f"{idx:02d}. [{t['dt']}] {status:<4} | Spent: ${spent:6.2f} | Payout: ${recv:6.2f} | PnL: {pnl:+6.2f} | Cumulative: {total_won - total_lost:+6.2f} | Buys: {buys_summary} | {t['title']}")

print("====================================================================================================")
print(f"Total Wins: {aug20['wins']} | Total Losses: {aug20['losses']} | Win Rate: {aug20['wins']/(aug20['wins']+aug20['losses'])*100:.2f}%")
print(f"Total Won from 28 Wins : +${total_won:.2f}")
print(f"Total Lost from 1 Loss : -${total_lost:.2f}")
print(f"Net P&L                : ${total_won - total_lost:+.2f}")
print("====================================================================================================")

# Now check details on the lost market
lost_trade = [t for t in aug20['details'] if t['status'] == 'LOSS'][0]
print("\nDETAILED ANALYSIS OF THE LOSS TRADE:")
print(f"Market: {lost_trade['title']}")
print(f"Condition ID: {lost_trade['cid']}")
print(f"Buys: {lost_trade['buys']}")
print(f"Redeems: {lost_trade['redeems']}")
print(f"Sells: {lost_trade['sells']}")

# Try querying Polymarket API for the conditionId
try:
    r = requests.get(f"https://clob.polymarket.com/markets/{lost_trade['cid']}", timeout=10)
    print("Market details:", r.json())
except Exception as e:
    print("CLOB lookup:", e)

try:
    r = requests.get(f"https://gamma-api.polymarket.com/markets?condition_id={lost_trade['cid']}", timeout=10)
    print("Gamma details:", r.json())
except Exception as e:
    print("Gamma lookup:", e)
