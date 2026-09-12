import os
import sys
import time
import json
import ssl
import threading
import datetime
import websocket

sys.stdout.reconfigure(encoding='utf-8')

LIVE_WS_URL = "wss://ws-live-data.polymarket.com/"
WS_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def make_ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

class WSFeed:
    def __init__(self):
        self._price = None
        self._ts_ms = None
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._stopped = False
        self._ws_app = None
        self.ticks = []

    def start(self):
        ssl_ctx = make_ssl_ctx()

        def on_open(ws):
            ws.send(json.dumps({
                "action": "subscribe",
                "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}],
            }))

        def on_message(ws, raw):
            if not raw:
                return
            try:
                msg = json.loads(raw)
            except Exception:
                return
            if msg.get("topic") != "crypto_prices_chainlink":
                return
            p = msg.get("payload", {})
            if p.get("symbol") != "btc/usd":
                return
            with self._lock:
                val = float(p.get("value"))
                ts = int(p.get("timestamp"))
                self._price = val
                self._ts_ms = ts
                self.ticks.append((ts, val))
                self._ready.set()

        def on_close(ws, close_status_code, close_msg):
            if not self._stopped:
                time.sleep(2)
                self.start()

        def on_error(ws, err):
            pass

        app = websocket.WebSocketApp(
            LIVE_WS_URL, header=WS_HEADERS,
            on_open=on_open, on_message=on_message,
            on_close=on_close, on_error=on_error
        )
        self._ws_app = app
        threading.Thread(
            target=lambda: app.run_forever(
                sslopt={"context": ssl_ctx}, ping_interval=20, ping_timeout=10
            ),
            daemon=True,
        ).start()
        self._ready.wait(timeout=20)

    def price_at_or_after(self, ts_sec):
        target_ms = ts_sec * 1000
        with self._lock:
            for ts, price in self.ticks:
                if ts >= target_ms:
                    return price, ts
        return None

def main():
    print("=" * 80)
    print("🛰️ INITIALIZING EXACT POLYMARKET PTB CAPTURE ENGINE")
    print("=" * 80)
    
    ws = WSFeed()
    ws.start()
    print("✅ Connected to Polymarket Chainlink Live Stream.")
    
    # Calculate next 5-min window
    now = time.time()
    w_s = int(now // 300) * 300 + 300
    w_e = w_s + 300
    
    dt_str = datetime.datetime.fromtimestamp(w_s, tz=datetime.timezone.utc).strftime("%H:%M:%S UTC")
    slug = f"btc-updown-5m-{w_s}"
    
    print(f"🎯 Target Window Open : {dt_str} (Slug: {slug})")
    print(f"⏳ Waiting for boundary...")
    
    while time.time() < w_s:
        rem = int(w_s - time.time())
        sys.stdout.write(f"\rCountdown: T-{rem:02d}s | Current Live Price: ${(ws._price or 0):,.2f}   ")
        sys.stdout.flush()
        time.sleep(0.5)
        
    print(f"\n\n🚨 [{datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S.%f')[:-3]} UTC] Window Opened! Waiting for first tick at or after boundary...")
    
    ptb = None
    ptb_ts = None
    deadline = time.time() + 30
    while time.time() < deadline:
        res = ws.price_at_or_after(w_s)
        if res:
            ptb, ptb_ts = res
            lag = (ptb_ts - w_s * 1000) / 1000.0
            print("=" * 80)
            print(f"📌 OFFICIAL POLYMARKET PRICE TO BEAT (PTB):")
            print(f"   • Strike Price : ${ptb:,.2f}")
            print(f"   • Window Open  : {dt_str}")
            print(f"   • Timestamp ms : {ptb_ts}")
            print(f"   • Lag          : +{lag:.3f}s after boundary")
            print(f"   • Market Slug  : {slug}")
            print("=" * 80)
            break
        time.sleep(0.05)

if __name__ == "__main__":
    main()
