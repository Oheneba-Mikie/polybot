import requests
import json
import datetime

DATA_HOST = "https://data-api.polymarket.com"
POLYMARKET_ADDRESS = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"

url = f"{DATA_HOST}/trades?user={POLYMARKET_ADDRESS}&limit=10"
r = requests.get(url).json()

print("="*90)
print("FORENSIC AUDIT OF TRADES BETWEEN 20:08 AND 20:15 UTC:")
print("="*90)
for t in r:
    ts = t.get("timestamp", 0)
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    side = t.get("side", "")
    px = float(t.get("price", 0))
    sz = float(t.get("size", 0))
    mkt = t.get("market", "")
    tx = t.get("transactionHash", "")[:20]
    print(f"{dt_str} | {side:<4} | ${px:.2f} | {sz:.2f} sh | tx: {tx} | market: {mkt}")
