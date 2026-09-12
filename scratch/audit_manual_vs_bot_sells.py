import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

addr = "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"

print("="*95)
print(f"📊 FULL TRADE LEDGER & TIMING AUDIT FOR WALLET: {addr}")
print("="*95)

try:
    r_tr = requests.get(f"https://data-api.polymarket.com/trades?user={addr}&limit=20").json()
    print(f"Total Trades Found: {len(r_tr)}\n")
    # Print oldest to newest
    for idx, t in enumerate(reversed(r_tr), 1):
        dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t.get("timestamp", 0)))
        side = t.get("side")
        sz = float(t.get("size", 0))
        px = float(t.get("price", 0))
        val = sz * px
        title = t.get("title")
        out = t.get("outcome")
        tx = t.get("transactionHash", "")[:14] + "..."
        print(f"  [{idx:02d}] {dt} | {side:<4} {sz:6.3f} sh of {out:<4} @ ${px:.3f} (Val: ${val:.2f}) | TX: {tx} | {title}")
except Exception as e:
    print("Error querying trades:", e)

print("="*95)
