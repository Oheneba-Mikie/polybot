#!/usr/bin/env python3
"""
track_ws.py — Live tracker for Polymarket's BTC/USD Chainlink WS feed.

Runs until the END of the current 5-minute window, then prints a final
summary and exits — so you can compare the result against Polymarket's
resolved outcome.

Usage:
    python track_ws.py
"""

import json
import os
import ssl
import sys
import time
import datetime
import threading
import websocket

LIVE_WS_URL = "wss://ws-live-data.polymarket.com/"


def make_ssl_context():
    ctx = ssl.create_default_context()
    for p in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(p):
            ctx.load_verify_locations(p)
            break
    return ctx


WS_HEADERS = {
    "Origin": "https://polymarket.com",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
}


def window_start(ts_sec: float) -> int:
    return int(ts_sec // 300) * 300


def fmt_time(ts_sec: float) -> str:
    return datetime.datetime.fromtimestamp(ts_sec).strftime("%H:%M:%S")


def fmt_window(start_sec: int) -> str:
    return f"{fmt_time(start_sec)} → {fmt_time(start_sec + 300)}"


# --- shared state ---
state = {
    "window_start": None,       # unix ts of current window open
    "window_end": None,         # unix ts of current window close
    "price_to_beat": None,      # first tick price this window
    "last_price": None,         # most recent tick price
    "tick_count": 0,
    "done": False,
}
ws_ref = [None]                 # so the shutdown timer can call ws.close()


def print_final_summary():
    ptb = state["price_to_beat"]
    last = state["last_price"]
    if ptb is None or last is None:
        print("\n  (no ticks received — cannot summarise)")
        return
    diff = last - ptb
    direction = "UP ▲" if diff > 0 else "DOWN ▼"
    print()
    print("=" * 70)
    print(f"  ⏰ WINDOW CLOSED: {fmt_window(state['window_start'])}")
    print(f"  📌 Price to Beat  (window open)  : ${ptb:>10,.2f}")
    print(f"  🏁 Final Price    (window close)  : ${last:>10,.2f}")
    print(f"  📊 Net move                       : {diff:>+10.2f}")
    print(f"  🎯 Result                         : {direction}")
    print(f"  🔢 Ticks seen this window         : {state['tick_count']}")
    print("=" * 70)
    print()
    print("  → Compare this result against Polymarket's resolved outcome!")
    print()


def shutdown_at_window_end():
    """Background thread: sleeps until window ends, then closes the WS."""
    end = state["window_end"]
    remaining = end - time.time()
    if remaining > 0:
        time.sleep(remaining + 0.5)   # +0.5s to make sure the last tick lands
    state["done"] = True
    print_final_summary()
    if ws_ref[0] is not None:
        ws_ref[0].close()


def on_message(ws, raw):
    if not raw or state["done"]:
        return
    try:
        msg = json.loads(raw)
    except Exception:
        return

    if msg.get("topic") != "crypto_prices_chainlink":
        return
    payload = msg.get("payload", {})
    if payload.get("symbol") != "btc/usd":
        return

    ts_ms = payload.get("timestamp")
    price = payload.get("value")
    if ts_ms is None or price is None:
        return

    ts_sec = ts_ms / 1000.0
    now_sec = time.time()
    cur_win = window_start(ts_sec)
    cur_win_end = cur_win + 300
    remaining = int(cur_win_end - now_sec)
    state["tick_count"] += 1
    state["last_price"] = price

    # First tick ever — set up window and start shutdown timer
    if state["window_start"] is None:
        state["window_start"] = cur_win
        state["window_end"] = cur_win_end
        state["price_to_beat"] = price

        secs_into = int(now_sec - cur_win)
        print()
        print(f"  📍 Joined mid-window: {fmt_window(cur_win)}")
        print(f"     Started {secs_into}s into the window ({remaining}s remaining)")
        print(f"  📌 PRICE TO BEAT (first tick seen): ${price:,.2f}")
        print(f"     ⚠️  Note: true Price to Beat was at {fmt_time(cur_win)} — "
              f"this is {secs_into}s late")
        print()

        # Kick off the shutdown timer
        t = threading.Thread(target=shutdown_at_window_end, daemon=True)
        t.start()

    ptb = state["price_to_beat"]
    diff = price - ptb
    diff_str = f"{diff:+.2f}"
    arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "─")

    print(
        f"  tick #{state['tick_count']:>3}  WS={fmt_time(ts_sec)}  "
        f"BTC/USD: ${price:>10,.2f}  {arrow} {diff_str:>8}  "
        f"vs ptb=${ptb:,.2f}  "
        f"ends in {remaining:>3}s"
    )


def on_open(ws):
    ws_ref[0] = ws
    now = time.time()
    cur_win = window_start(now)
    ends_at = cur_win + 300
    remaining = int(ends_at - now)
    print(f"Connected to {LIVE_WS_URL}")
    print(f"Current window: {fmt_window(cur_win)}  ({remaining}s remaining)")
    print("Subscribing... waiting for first tick (~1s)")
    print("-" * 70)
    ws.send(json.dumps({
        "action": "subscribe",
        "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}],
    }))


def on_error(ws, err):
    if not state["done"]:
        print(f"WS ERROR: {err}")


def on_close(ws, code, msg):
    if not state["done"]:
        print(f"WS CLOSED ({code})")


if __name__ == "__main__":
    ctx = make_ssl_context()
    app = websocket.WebSocketApp(
        LIVE_WS_URL,
        header=WS_HEADERS,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    try:
        app.run_forever(sslopt={"context": ctx}, ping_interval=20)
    except KeyboardInterrupt:
        print("\nStopped early.")
