import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST = "https://data-api.polymarket.com"
cid = "0x431faba7cfef00ac7b342f8f491a211d37602e814d549adc32065a53495c4e8c"

r = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=500", timeout=5).json()
trades = sorted(r, key=lambda x: x.get("timestamp", 0))

print("Total trades:", len(trades))
for t in trades[:40]:
    ts_sec = t.get("timestamp", 0)
    dt = datetime.datetime.fromtimestamp(ts_sec, datetime.timezone.utc).strftime("%H:%M:%S")
    side = t.get("outcome", "")
    px = float(t.get("price", 0))
    sz = float(t.get("size", 0))
    side_type = t.get("side", "")
    print(f"[{dt}] {side:<4} | ${px:<7.4f} | {sz:<8.2f} sh | {side_type}")
