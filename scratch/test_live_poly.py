import os
import sys
import time
import json
import ssl
import websocket

sys.stdout.reconfigure(encoding='utf-8')

LIVE_WS_URL = "wss://ws-live-data.polymarket.com/"
WS_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def main():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    ticks = []

    def on_open(ws):
        print("Connected to wss://ws-live-data.polymarket.com/")
        payload = {
            "action": "subscribe",
            "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}]
        }
        ws.send(json.dumps(payload))

    def on_message(ws, raw):
        try:
            msg = json.loads(raw)
            if msg.get("topic") == "crypto_prices_chainlink":
                p = msg.get("payload", {})
                if p.get("symbol") == "btc/usd":
                    val = p.get("value")
                    ts = p.get("timestamp")
                    print(f"  ⚡ Live Chainlink Tick: ${float(val):,.2f} (Timestamp: {ts})")
                    ticks.append((val, ts))
                    if len(ticks) >= 5:
                        ws.close()
        except Exception as e:
            print("Error parsing msg:", e)

    def on_error(ws, err):
        print("WS Error:", err)

    def on_close(ws, c, m):
        print("WS Closed.")

    ws_app = websocket.WebSocketApp(
        LIVE_WS_URL,
        header=WS_HEADERS,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws_app.run_forever(sslopt={"context": ctx})

if __name__ == "__main__":
    main()
