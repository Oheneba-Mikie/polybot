import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"
user_addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"

print("="*95)
print("💰 FULL WALLET & POSITION AUDIT: WHERE IS THE MONEY?")
print("="*95)

# 1. Check positions
r_pos = requests.get(f"{DATA_HOST}/positions?user={user_addr}").json()
print("📊 Current Open / Unredeemed Positions:")
total_pos_val = 0.0
for p in r_pos:
    title = p.get("title")
    out = p.get("outcome")
    sz = float(p.get("size", 0))
    avg_p = p.get("avgPrice")
    cur_p = float(p.get("curPrice", 0))
    val = float(p.get("currentValue", 0))
    if val > 0 or sz > 1.0:
        total_pos_val += val
        print(f"  • {title} | {out}: {sz:.4f} shares (Avg Price: ${avg_p}, Current: ${cur_p:.3f}, Value: ${val:.2f})")

print(f"\n💵 Total Value in Unredeemed / Winning Shares: ${total_pos_val:.2f} USDC")

# 2. Check recent trades
r_tr = requests.get(f"{DATA_HOST}/trades?user={user_addr}&limit=10").json()
print("\n📜 Recent 5 Trades on Polymarket Ledger:")
for t in r_tr[:5]:
    dt = time.strftime("%H:%M:%S UTC", time.gmtime(t.get("timestamp", 0)))
    side = t.get("side")
    out = t.get("outcome")
    sz = t.get("size")
    px = t.get("price")
    title = t.get("title")
    print(f"  [{dt}] {side} {sz} shares of {out} @ ${px} | {title}")

# 3. Check live Railway API state
r_state = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state").json()
print(f"\n🤖 Live Railway State Balance Field: ${r_state.get('balance_usdc')} USDC")
print(f"🏷️ Railway Phase Field: {r_state.get('phase')}")

print("="*95)
