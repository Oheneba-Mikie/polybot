import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
WALLET = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"

print("="*95)
print(f"📜 COMPLETE RAW TRADE LOG FROM POLYMARKET DATA API FOR PROXY: {WALLET}")
print("="*95)

r = requests.get(f"{DATA_HOST}/trades?user={WALLET}&limit=50", timeout=5).json()
for t in r:
    ts = t.get("timestamp", 0)
    dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    side = t.get("side", "")
    outcome = t.get("outcome", "")
    sz = float(t.get("size", 0))
    usdc = float(t.get("usdcSize", 0))
    px = float(t.get("price", 0))
    title = t.get("title", "")
    print(f"[{dt}] {side:<4} {outcome:<4} | {sz:>6.2f} sh (${usdc:>6.2f}) @ ${px:.4f} | {title}")

print("="*95)
