import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*105)
print("🔍 AUDITING BOT ACTIVITY AT T-12s (22:09:48) & EXACT ON-CHAIN DEPOSIT TIMESTAMPS")
print("="*105)

addr = "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"

# 1. Query live bot state and logs right now
print("1. LIVE CONTAINER STATE & RECENT LOGS:")
try:
    r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=4).json()
    print(f"   Status:     {r.get('status')}")
    print(f"   Phase:      {r.get('phase')}")
    print(f"   Balance:    ${r.get('balance'):.2f}")
    print(f"   Trades:     {r.get('total_trades')}")
    print(f"   Last Trade: {r.get('last_trade')}")
    print("   Logs (last 8):")
    for l in r.get("logs", [])[-8:]:
        print(f"     {l}")
except Exception as e:
    print("   State query error:", e)

# 2. Query exact on-chain deposit / transfer history for wallet
print("\n2. ON-CHAIN DEPOSIT / TRANSACTION TIMESTAMPS FOR WALLET:")
try:
    # Query Polygon USDC transfers or Polymarket activity
    r_act = requests.get(f"https://data-api.polymarket.com/activity?user={addr}&limit=10", timeout=4).json()
    print(f"   Found {len(r_act)} on-chain activity entries for {addr}:")
    for act in r_act:
        t_ts = act.get("timestamp", 0)
        t_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t_ts))
        print(f"     • [{t_str}] Type: {act.get('type')} | Amount: ${float(act.get('size', 0)):.2f} | Title: {act.get('title', 'Transfer/Deposit')}")
except Exception as e:
    print("   Activity error:", e)

print("="*105)
