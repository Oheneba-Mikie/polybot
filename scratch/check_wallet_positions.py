import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
user_addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"

print("="*95)
print("🔍 CHECKING WALLET POSITIONS & ACTIVE SHARES ON POLYMARKET:")
print("="*95)

r_pos = requests.get(f"{DATA_HOST}/positions?user={user_addr}").json()
print("Live Positions:")
for p in r_pos:
    title = p.get("title")
    out = p.get("outcome")
    sz = p.get("size")
    avg_p = p.get("avgPrice")
    cur_p = p.get("curPrice")
    val = p.get("currentValue")
    print(f"  • {title} | {out}: {sz} shares (Avg Price: ${avg_p}, Current: ${cur_p}, Value: ${val})")

r_tr = requests.get(f"{DATA_HOST}/trades?user={user_addr}&limit=5").json()
print("\nRecent 5 Trades:")
for t in r_tr:
    dt = time.strftime("%H:%M:%S UTC", time.gmtime(t.get("timestamp", 0)))
    side = t.get("side")
    out = t.get("outcome")
    sz = t.get("size")
    px = t.get("price")
    title = t.get("title")
    print(f"  [{dt}] {side} {sz} shares of {out} @ ${px} | {title}")

print("="*95)
