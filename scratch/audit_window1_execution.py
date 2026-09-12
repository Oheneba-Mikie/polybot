import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*105)
print("🔍 AUDITING WINDOW 1 EXECUTION AT T-12s (22:24:48 UTC)")
print("="*105)

addr = "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"

# 1. Query Railway bot state
try:
    r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=4).json()
    print("🤖 Live Bot State:")
    print(f"  • Status:     {r.get('status')}")
    print(f"  • Phase:      {r.get('phase')}")
    print(f"  • Balance:    ${r.get('balance'):.2f}")
    print(f"  • Trades:     {r.get('total_trades')}")
    print(f"  • Wins:       {r.get('wins')}")
    print(f"  • Streak:     {r.get('streak')} W")
    print(f"  • Last Trade: {r.get('last_trade')}")
    print(f"  • Strike:     ${r.get('strike_price')}")
    print(f"  • Live Gap:   ${r.get('gap') or 0:.2f}")
    print("\n📜 Full Window 1 Execution Logs:")
    for l in r.get("logs", [])[-15:]:
        print(f"  {l}")
except Exception as e:
    print("State query error:", e)

# 2. Query Polymarket live trades on wallet
print("\n" + "="*105)
print("📊 POLYMARKET ON-CHAIN WALLET RECENT TRADES:")
try:
    r_trades = requests.get(f"https://data-api.polymarket.com/trades?user={addr}&limit=5", timeout=4).json()
    print(f"Total Recent Trades on Wallet: {len(r_trades)}")
    for t in r_trades:
        dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t.get("timestamp", 0)))
        print(f"  • [{dt}] {t.get('side')} {t.get('size')} sh @ ${t.get('price')} | {t.get('title')}")
except Exception as e:
    print("Trade query error:", e)

print("="*105)
