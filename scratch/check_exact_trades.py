import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
WALLET = "0x89B489569F1B2384ee02E958444aF6091219bfe9"

r = requests.get(f"{DATA_HOST}/trades?maker={WALLET}&limit=10", timeout=5).json()
if not r:
    r = requests.get(f"{DATA_HOST}/trades?taker={WALLET}&limit=10", timeout=5).json()

for t in r:
    ts_sec = t.get("timestamp", 0)
    dt = datetime.datetime.fromtimestamp(ts_sec, datetime.timezone.utc).strftime("%H:%M:%S")
    side = t.get("side", "")
    outcome = t.get("outcome", "")
    px = float(t.get("price", 0))
    sz = float(t.get("size", 0))
    title = t.get("title", "")[:35]
    print(f"[{dt}] {side:<4} | {outcome:<4} | {sz:.2f} sh @ ${px:.4f} | {title}")
