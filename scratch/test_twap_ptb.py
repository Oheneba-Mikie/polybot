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

class ChainlinkTWAPFeed:
    def __init__(self):
        self._lock = threading.Lock()
        self.ticks = []  # list of (timestamp_ms, price)
        self.connected = False
        self._stopped = False
        self._ws_app = None

    def start(self):
        ssl_ctx = make_ssl_ctx()

        def on_open(ws):
            self.connected = True
            ws.send(json.dumps({
                "action": "subscribe",
                "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}],
            }))

        def on_message(ws, raw):
            try:
                msg = json.loads(raw)
                if msg.get("topic") == "crypto_prices_chainlink":
                    p = msg.get("payload", {})
                    if p.get("symbol") == "btc/usd":
                        val = float(p.get("value"))
                        ts = int(p.get("timestamp"))
                        with self._lock:
                            self.ticks.append((ts, val))
                            # Keep only last 10 minutes of ticks
                            cutoff = ts - 600_000
                            self.ticks = [t for t in self.ticks if t[0] >= cutoff]
            except Exception:
                pass

        def on_close(ws, c, m):
            if not self._stopped:
                time.sleep(1)
                self.start()

        def on_error(ws, err):
            pass

        app = websocket.WebSocketApp(
            LIVE_WS_URL,
            header=WS_HEADERS,
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error
        )
        self._ws_app = app
        threading.Thread(
            target=lambda: app.run_forever(
                sslopt={"context": ssl_ctx}, ping_interval=20, ping_timeout=10
            ),
            daemon=True
        ).start()

    def get_latest(self):
        with self._lock:
            if self.ticks:
                return self.ticks[-1][1], self.ticks[-1][0]
            return None, None

    def compute_twap(self, end_ts_sec, lookback_sec=60):
        """
        Computes 60-second TWAP from (end_ts_sec - lookback_sec) to end_ts_sec.
        """
        start_ms = (end_ts_sec - lookback_sec) * 1000
        end_ms = end_ts_sec * 1000

        with self._lock:
            # Filter ticks in lookback window
            window_ticks = [t for t in self.ticks if start_ms <= t[0] <= end_ms]
            
            # If we don't have ticks at the exact boundary, find the last tick before start_ms
            prev_ticks = [t for t in self.ticks if t[0] < start_ms]
            seed_price = prev_ticks[-1][1] if prev_ticks else (window_ticks[0][1] if window_ticks else None)

            if not window_ticks and seed_price is None:
                return None, 0

            # Build continuous timeline for time-weighting
            timeline = []
            curr_time = start_ms
            curr_price = seed_price if seed_price is not None else window_ticks[0][1]

            for ts, px in window_ticks:
                if ts > curr_time:
                    timeline.append((curr_price, ts - curr_time))
                    curr_time = ts
                    curr_price = px

            if curr_time < end_ms:
                timeline.append((curr_price, end_ms - curr_time))

            total_weight = sum(w for _, w in timeline)
            if total_weight == 0:
                return curr_price, len(window_ticks)

            twap = sum(px * w for px, w in timeline) / total_weight
            return twap, len(window_ticks)

def main():
    print("=" * 80)
    print("📊 LIVE CHAINLINK 60-SECOND TWAP PRICE-TO-BEAT ENGINE")
    print("=" * 80)

    feed = ChainlinkTWAPFeed()
    feed.start()
    
    print("Connecting to Polymarket Chainlink Stream...")
    for _ in range(20):
        p, ts = feed.get_latest()
        if p is not None:
            print(f"✅ Feed Connected! Current Live BTC Price: ${p:,.2f}")
            break
        time.sleep(0.5)

    now = time.time()
    w_s = int(now // 300) * 300 + 300
    dt_str = datetime.datetime.fromtimestamp(w_s, tz=datetime.timezone.utc).strftime("%H:%M:%S UTC")
    slug = f"btc-updown-5m-{w_s}"
    
    print(f"\n🎯 Target Window: {dt_str} (Slug: {slug})")
    print(f"📐 Lookback Window: {datetime.datetime.fromtimestamp(w_s-60, tz=datetime.timezone.utc).strftime('%H:%M:%S')} → {dt_str} (60s TWAP)")
    print("=" * 80)

    while time.time() < w_s:
        rem = int(w_s - time.time())
        p, _ = feed.get_latest()
        # Preview current running TWAP
        running_twap, tick_cnt = feed.compute_twap(int(time.time()), 60)
        sys.stdout.write(f"\r⏳ Countdown: T-{rem:02d}s | Live Price: ${(p or 0):,.2f} | Running 60s TWAP: ${(running_twap or 0):,.2f} (Ticks: {tick_cnt}) ")
        sys.stdout.flush()
        time.sleep(0.5)

    # Allow slight buffer for last tick at boundary to arrive
    time.sleep(0.3)
    official_twap, total_ticks = feed.compute_twap(w_s, 60)

    print("\n\n" + "=" * 80)
    print(f"🎯 OFFICIAL 60-SECOND TWAP PRICE-TO-BEAT FOR [{dt_str}]:")
    print("=" * 80)
    print(f"   • Price-To-Beat (60s TWAP) : ${official_twap:,.2f}")
    print(f"   • Total Ticks Sampled      : {total_ticks}")
    print(f"   • Market Slug              : {slug}")
    print(f"   • Oracle Config            : btc-5m-twap-60 (Chainlink TWAP 60s)")
    print("=" * 80)

if __name__ == "__main__":
    main()
