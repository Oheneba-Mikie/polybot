import json
import time
import ssl
import websocket
import requests

def get_live_market_token_ids():
    now_ts = int(time.time())
    round_start = (now_ts // 300) * 300
    slug = f"btc-updown-5m-{round_start}"
    url = f"https://gamma-api.polymarket.com/events?slug={slug}"
    res = requests.get(url, timeout=5).json()
    if res and len(res) > 0:
        markets = res[0].get("markets", [])
        if markets:
            m = markets[0]
            clob_ids = json.loads(m.get("clobTokenIds", "[]"))
            print(f"Resolved Slug: {slug}")
            print(f"Token IDs: {clob_ids}")
            return clob_ids
    print("Failed to resolve current market slug, using fallback search...")
    res2 = requests.get("https://gamma-api.polymarket.com/events?limit=10&active=true&closed=false&q=btc-updown-5m").json()
    for ev in res2:
        for m in ev.get("markets", []):
            clob_ids = json.loads(m.get("clobTokenIds", "[]"))
            print(f"Fallback Market: {m.get('slug')} -> Token IDs: {clob_ids}")
            return clob_ids
    return None

def test_clob_websocket():
    token_ids = get_live_market_token_ids()
    if not token_ids:
        print("No active token IDs found.")
        return

    ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    print(f"\nConnecting to Polymarket CLOB WebSocket at: {ws_url}")

    msg_count = 0
    start_time = time.time()

    def on_open(ws):
        print("Connected to CLOB WS!")
        # Subscribe message format for Polymarket CLOB WS
        sub_msg = {
            "type": "market",
            "assets_ids": token_ids
        }
        print(f"Sending Subscription Payload: {json.dumps(sub_msg)}")
        ws.send(json.dumps(sub_msg))

    def on_message(ws, message):
        nonlocal msg_count
        msg_count += 1
        elapsed = time.time() - start_time
        try:
            data = json.loads(message)
            msg_type = data.get("event_type") or data.get("type") or "unknown"
            asset_id = data.get("asset_id", "N/A")
            print(f"[{elapsed:.2f}s] [MSG #{msg_count}] Event: '{msg_type}' | Asset: ...{str(asset_id)[-8:]} | Full Payload: {message[:120]}...")
        except Exception as e:
            print(f"[{elapsed:.2f}s] [MSG #{msg_count}] Raw Text: {message[:120]}... (Err: {e})")

        if msg_count >= 15 or elapsed >= 10:
            print(f"\nTest complete! Received {msg_count} real-time pushed events in {elapsed:.2f} seconds.")
            ws.close()

    def on_error(ws, error):
        print(f"WS Error: {error}")

    def on_close(ws, close_status_code, close_msg):
        print(f"WS Closed: {close_status_code} - {close_msg}")

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

if __name__ == "__main__":
    test_clob_websocket()
