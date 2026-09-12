import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

addr = "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"

print("="*95)
print(f"📊 LIVE TRADES & CONTAINER LOGS FOR MOST RECENT TRADE ({addr}):")
print("="*95)

try:
    r_tr = requests.get(f"https://data-api.polymarket.com/trades?user={addr}&limit=10").json()
    print("Recent Trades:")
    for idx, t in enumerate(r_tr[:6], 1):
        dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t.get("timestamp", 0)))
        side = t.get("side")
        sz = float(t.get("size", 0))
        px = float(t.get("price", 0))
        val = sz * px
        title = t.get("title")
        out = t.get("outcome")
        print(f"  [{idx:02d}] {dt} | {side:<4} {sz:6.3f} sh of {out:<4} @ ${px:.3f} (Val: ${val:.2f}) | {title}")
except Exception as e:
    print("Error querying trades:", e)

print("\n" + "="*95)
print("📋 RAILWAY BOT CONTAINER LOGS:")
print("="*95)
try:
    r_state = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=6).json()
    for l in r_state.get("logs", [])[-25:]:
        print(f"  {l}")
except Exception as e:
    print("Error querying Railway state:", e)

print("="*95)
