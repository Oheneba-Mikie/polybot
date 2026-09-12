import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print(f"📊 LIVE CLOUD BOT STATUS & TRADE AUDIT AT {datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S UTC')}")
print("="*95)

# Query Railway Live State
try:
    r_state = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=4).json()
    print(f"Status:            {r_state.get('status')}")
    print(f"Current Candle:    {r_state.get('current_candle')}")
    print(f"Wallet Balance:    ${r_state.get('balance')}")
    print(f"Total Snipes:      {r_state.get('total_trades')}")
    print(f"Wins:              {r_state.get('wins')}")
    print(f"Losses:            {r_state.get('losses')}")
    print(f"Total Net Profit:  +${r_state.get('total_profit_usdc'):.4f} USDC")
    print(f"Last Trade:        {r_state.get('last_trade')}")
    print("\nRecent Cloud Logs:")
    for l in r_state.get("logs", [])[-12:]:
        print(f"  {l}")
except Exception as e:
    print(f"Railway dashboard query error: {e}")

# Query Polymarket on-chain trades for the proxy wallet
WALLET = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
print("\n--- POLYMARKET CLOB RECENT EXECUTIONS (LAST 2 HOURS) ---")
try:
    r_tr = requests.get(f"https://data-api.polymarket.com/trades?user={WALLET}&limit=10", timeout=4).json()
    for t in r_tr:
        ts = t.get("timestamp", 0)
        dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        side = t.get("side", "")
        out = t.get("outcome", "")
        sz = float(t.get("size", 0))
        px = float(t.get("price", 0))
        title = t.get("title", "")
        print(f"[{dt}] {side:<4} {out:<4} | {sz:>5.2f} sh @ ${px:.4f} | {title}")
except Exception as e:
    print(f"Data API error: {e}")

print("="*95)
