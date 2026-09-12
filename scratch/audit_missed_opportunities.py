import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*105)
print("🔍 AUDITING CURRENT STATUS, WALLET BALANCE, AND MISSED OPPORTUNITIES")
print("="*105)

addr = "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"

# 1. Query Railway State
print("1. Railway Live Container State:")
try:
    r_state = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=6).json()
    print(f"   Status: {r_state.get('status')}")
    print(f"   Phase:  {r_state.get('phase')}")
    print(f"   Strike: {r_state.get('strike_price')}")
    print(f"   Balance in Bot State: {r_state.get('balance')}")
    print(f"   Recent Logs (last 5):")
    for l in r_state.get("logs", [])[-5:]:
        print(f"     {l}")
except Exception as e:
    print("   State Error:", e)

# 2. Query Polymarket live balance & positions
print("\n2. Live Polymarket Wallet Status:")
try:
    r_pos = requests.get(f"https://data-api.polymarket.com/positions?user={addr}").json()
    print(f"   Open Positions: {len(r_pos)}")
    for p in r_pos:
        sz = float(p.get("size", 0))
        if sz > 0.001:
            print(f"     • {sz:.3f} sh of {p.get('outcome')} on {p.get('title')} (Value: ${float(p.get('currentValue', 0)):.2f})")
except Exception as e:
    print("   Pos Error:", e)

try:
    r_trades = requests.get(f"https://data-api.polymarket.com/trades?user={addr}&limit=5").json()
    print(f"   Recent Trades on Wallet: {len(r_trades)}")
    for t in r_trades:
        dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t.get("timestamp", 0)))
        print(f"     • [{dt}] {t.get('side')} {t.get('size')} sh @ ${t.get('price')} | {t.get('title')}")
except Exception as e:
    print("   Trade Error:", e)

print("="*105)
