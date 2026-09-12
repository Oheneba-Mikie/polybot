import requests
import json
import datetime
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print(f"📊 LIVE CLOUD BOT STATE & RECENT LOGS AT {datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S UTC')}")
print("="*95)

try:
    r_state = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=4).json()
    print(f"Status:          {r_state.get('status')}")
    print(f"Current Candle:  {r_state.get('current_candle')}")
    print(f"Phase:           {r_state.get('phase')}")
    print(f"Wallet Balance:  ${r_state.get('balance')}")
    print(f"Total Sprints:   {r_state.get('total_trades')}")
    print(f"Streak:          {r_state.get('streak')} Wins")
    print(f"Total Profit:    +${r_state.get('total_profit_usdc'):.2f} USDC")
    print(f"Last Trade:      {r_state.get('last_trade')}")
    print(f"Strike Price:    ${r_state.get('strike_price') or 0:.2f}")
    print(f"Chainlink BTC:   ${r_state.get('chainlink_price') or 0:.2f}")
    print(f"Current Move:    ${r_state.get('gap') or 0:.2f}")
    
    print("\nRecent Cloud Logs:")
    for l in r_state.get("logs", [])[-15:]:
        print(f"  {l}")
except Exception as e:
    print(f"Error querying Railway dashboard: {e}")

print("="*95)
