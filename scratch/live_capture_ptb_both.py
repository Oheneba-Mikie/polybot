import os
import sys
import time
import json
import ssl
import threading
import datetime
import requests
import websocket

sys.stdout.reconfigure(encoding='utf-8')

# ── 1. POLYMARKET LIVE CHAINLINK WS FEED ─────────────────────────────────────
POLY_WS_URL = "wss://ws-live-data.polymarket.com/"

class PolymarketLiveFeed:
    def __init__(self):
        self.latest_price = None
        self.latest_ts = None
        self.ticks = []
        self.lock = threading.Lock()
        self.connected = False
        
    def start(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        def on_open(ws):
            self.connected = True
            ws.send(json.dumps({
                "action": "subscribe",
                "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}]
            }))
            
        def on_message(ws, raw):
            try:
                msg = json.loads(raw)
                if msg.get("topic") == "crypto_prices_chainlink":
                    p = msg.get("payload", {})
                    if p.get("symbol") == "btc/usd":
                        val = float(p.get("value"))
                        ts = int(p.get("timestamp"))
                        with self.lock:
                            self.latest_price = val
                            self.latest_ts = ts
                            self.ticks.append((ts, val))
                            if len(self.ticks) > 1000:
                                self.ticks.pop(0)
            except Exception:
                pass

        def on_error(ws, err):
            pass

        def on_close(ws, c, m):
            self.connected = False

        ws_app = websocket.WebSocketApp(
            POLY_WS_URL,
            header={"User-Agent": "Mozilla/5.0"},
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        t = threading.Thread(target=lambda: ws_app.run_forever(sslopt={"context": ctx}, ping_interval=20, ping_timeout=10), daemon=True)
        t.start()

    def get_latest(self):
        with self.lock:
            return self.latest_price, self.latest_ts

    def get_price_at_or_after(self, target_ts_sec):
        target_ms = target_ts_sec * 1000
        with self.lock:
            for ts, price in self.ticks:
                if ts >= target_ms:
                    return price, ts
        return None, None

# ── 2. PREDICT.FUN / BINANCE FEED ──────────────────────────────────────────
class PredictFunFeed:
    def __init__(self):
        self.latest_mid = None
        self.latest_binance = None
        self.lock = threading.Lock()
        
    def poll_live_binance(self):
        try:
            r = requests.get("https://api.binance.com/api/v3/ticker/bookTicker?symbol=BTCUSDT", timeout=3).json()
            bid = float(r["bidPrice"])
            ask = float(r["askPrice"])
            mid = (bid + ask) / 2.0
            return mid, bid, ask
        except Exception:
            return None, None, None

    def poll_predict_fun_market(self):
        # Check active markets from predict.fun
        try:
            r = requests.get("https://api.predict.fun/v1/markets", timeout=3).json()
            return r
        except Exception:
            try:
                r2 = requests.get("https://api-testnet.predict.fun/v1/markets", timeout=3).json()
                return r2
            except Exception:
                return None

# ── 3. MAIN LIVE TRACKER ─────────────────────────────────────────────────────
def main():
    print("=" * 80)
    print("🔴 INITIALIZING LIVE PRICE-TO-BEAT CAPTURE: POLYMARKET VS PREDICT.FUN")
    print("=" * 80)

    poly_feed = PolymarketLiveFeed()
    poly_feed.start()
    predict_feed = PredictFunFeed()

    print("Connecting to Polymarket Live Chainlink WS...")
    for _ in range(30):
        p, ts = poly_feed.get_latest()
        if p is not None:
            print(f"✅ Polymarket WebSocket Connected! Current Price: ${p:,.2f}")
            break
        time.sleep(0.5)

    now = time.time()
    current_start = int(now // 300) * 300
    next_start = current_start + 300
    
    dt_curr = datetime.datetime.fromtimestamp(current_start, tz=datetime.timezone.utc).strftime('%H:%M:%S UTC')
    dt_next = datetime.datetime.fromtimestamp(next_start, tz=datetime.timezone.utc).strftime('%H:%M:%S UTC')
    
    print(f"\n📊 Current 5m Window: {dt_curr} (Started {int(now - current_start)}s ago)")
    print(f"🎯 Target Next Window: {dt_next} (Starts in {int(next_start - now)}s)")
    print("=" * 80)

    # Polymarket Slug for next market
    poly_slug_next = f"btc-updown-5m-{next_start}"
    print(f"Polymarket Slug: {poly_slug_next}")

    # Countdown loop
    while time.time() < next_start:
        secs_left = int(next_start - time.time())
        poly_p, _ = poly_feed.get_latest()
        mid, bid, ask = predict_feed.poll_live_binance()
        
        sys.stdout.write(f"\r⏳ Waiting for window open {dt_next} | T-{secs_left:02d}s | Poly WS: ${(poly_p or 0):,.2f} | Binance Mid: ${(mid or 0):,.2f} ")
        sys.stdout.flush()
        time.sleep(0.5)

    print(f"\n\n🚨 [{datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S.%f')[:-3]} UTC] 🏁 WINDOW TRIGGERED! CAPTURING PTB...")

    # Capture Polymarket PTB
    poly_ptb = None
    poly_tick_ts = None
    for _ in range(20):
        poly_ptb, poly_tick_ts = poly_feed.get_price_at_or_after(next_start)
        if poly_ptb is not None:
            break
        time.sleep(0.1)

    if poly_ptb is None:
        poly_ptb, poly_tick_ts = poly_feed.get_latest()

    # Capture Predict.fun / Binance Benchmark PTB
    binance_mid, b_bid, b_ask = predict_feed.poll_live_binance()

    lag_ms = (poly_tick_ts - next_start * 1000) if poly_tick_ts else 0

    print("=" * 80)
    print(f"🎯 CAPTURED PRICE-TO-BEAT FOR 5-MINUTE WINDOW [{dt_next}]:")
    print("=" * 80)
    print(f"  1. POLYMARKET PRICE-TO-BEAT (PTB):")
    print(f"     • Strike Price:  ${(poly_ptb or 0):,.2f}")
    print(f"     • Feed Source:   Polymarket Live Chainlink WS (crypto_prices_chainlink, btc/usd)")
    print(f"     • Tick Lag:      +{lag_ms} ms after :00.000")
    print(f"     • Market Slug:   {poly_slug_next}")
    print()
    print(f"  2. PREDICT.FUN PRICE-TO-BEAT (PTB):")
    print(f"     • Strike Price:  ${(binance_mid or 0):,.2f}")
    print(f"     • Feed Source:   Chainlink Data Streams / Binance Top-of-Book Mid (Bid: ${b_bid:,.2f} | Ask: ${b_ask:,.2f})")
    print(f"     • Market Ref:    BTC Up/Down 5m @ {next_start}")
    print("=" * 80)
    
    diff = abs(poly_ptb - binance_mid) if (poly_ptb and binance_mid) else 0
    print(f"  ⚡ Cross-Platform Strike Discrepancy: ${diff:.2f}")
    print("=" * 80)

if __name__ == "__main__":
    main()
