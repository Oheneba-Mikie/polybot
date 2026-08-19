import websocket
import json
import time
import requests
import ssl

now_ts = time.time()
w_start = int(now_ts // 300) * 300
slug = f"btc-updown-5m-{w_start}"
print(f"Connecting to current cycle: {slug}")

r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=10).json()
market = r[0]["markets"][0]
token_ids = json.loads(market["clobTokenIds"])
outcomes = json.loads(market["outcomes"])

up_id, down_id = None, None
for i, o in enumerate(outcomes):
    if str(o).lower() in ("up", "yes"):
        up_id = token_ids[i]
    else:
        down_id = token_ids[i]

print(f"UP: {up_id} | DN: {down_id}")

count = 0

def on_message(ws, msg):
    global count
    if msg == "PONG": return
    try:
        data = json.loads(msg)
        print(f"\n[RAW MSG #{count}] Type: {type(data)} | Keys: {list(data.keys()) if isinstance(data, dict) else len(data)}")
        print(json.dumps(data)[:300])
        count += 1
        if count >= 10:
            ws.close()
    except Exception as e:
        print(f"Err: {e}")

def on_open(ws):
    print("WS Connected. Sending subscription...")
    sub = {
        "type": "market",
        "assets_ids": [up_id, down_id],
        "custom_feature_enabled": True
    }
    ws.send(json.dumps(sub))

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

ws = websocket.WebSocketApp(
    "wss://ws-subscriptions-clob.polymarket.com/ws/market",
    on_open=on_open,
    on_message=on_message
)
ws.run_forever(sslopt={"context": ssl_ctx}, ping_interval=10, ping_timeout=5)
