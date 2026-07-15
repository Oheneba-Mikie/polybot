#!/usr/bin/env python3
"""
test_bet_timing.py — Find the latest second you can still bet in a 5-min window.

Connects to the WS feed, resolves the current market, then polls the CLOB
order book every second for the last 2 minutes of the window. Reports:
  - Last second with a valid best ask (i.e. you CAN still bet)
  - First second the order book goes empty (market is CLOSED to bets)

Usage:
    python test_bet_timing.py

Run this and wait — it automatically handles the window timing.
"""

import json
import os
import ssl
import sys
import time
import datetime
import threading
import requests
import websocket

LIVE_WS_URL  = "wss://ws-live-data.polymarket.com/"
GAMMA_HOST   = "https://gamma-api.polymarket.com"
CLOB_HOST    = "https://clob.polymarket.com"


# ── SSL + headers ────────────────────────────────────────────────────────────
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


# ── Window helpers ────────────────────────────────────────────────────────────
def window_start(ts=None):
    t = ts or time.time()
    return int(t // 300) * 300

def window_end(ts=None):
    return window_start(ts) + 300

def current_slug(ts=None):
    return f"btc-updown-5m-{window_start(ts)}"

def fmt(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")


# ── Gamma: resolve market tokens ──────────────────────────────────────────────
def resolve_market(slug, timeout=10):
    resp = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=timeout)
    resp.raise_for_status()
    events = resp.json()
    if not events:
        return None
    market = events[0]["markets"][0]
    token_ids = json.loads(market.get("clobTokenIds") or "[]")
    outcomes  = json.loads(market.get("outcomes") or "[]")
    up_id, down_id = token_ids[0], token_ids[1]
    for i, o in enumerate([str(x).lower() for x in outcomes]):
        if o in ("up","yes"):   up_id   = token_ids[i]
        elif o in ("down","no"): down_id = token_ids[i]
    return {"slug": slug, "up_id": up_id, "down_id": down_id,
            "title": market.get("question", slug)}


# ── CLOB: order book snapshot ────────────────────────────────────────────────
def get_book_snapshot(token_id, timeout=3):
    """Returns (best_ask_price, num_asks, best_bid_price, num_bids) or None on error."""
    try:
        r = requests.get(f"{CLOB_HOST}/book", params={"token_id": token_id}, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        asks = data.get("asks", [])
        bids = data.get("bids", [])
        best_ask = float(min(asks, key=lambda a: float(a["price"]))["price"]) if asks else None
        best_bid = float(max(bids, key=lambda b: float(b["price"]))["price"]) if bids else None
        return best_ask, len(asks), best_bid, len(bids)
    except Exception as e:
        return None, 0, None, 0


# ── Live WS for price ────────────────────────────────────────────────────────
_ws_price = [None]
_ws_ts    = [None]
_ws_lock  = threading.Lock()

def _ws_on_msg(ws, raw):
    if not raw: return
    try:
        msg = json.loads(raw)
    except: return
    if msg.get("topic") != "crypto_prices_chainlink": return
    p = msg.get("payload", {})
    if p.get("symbol") != "btc/usd": return
    with _ws_lock:
        _ws_price[0] = p.get("value")
        _ws_ts[0]    = p.get("timestamp")

def start_ws():
    ctx = make_ssl_context()
    app = websocket.WebSocketApp(
        LIVE_WS_URL, header=WS_HEADERS,
        on_message=_ws_on_msg,
        on_open=lambda ws: ws.send(json.dumps({
            "action": "subscribe",
            "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}]
        })),
    )
    t = threading.Thread(
        target=lambda: app.run_forever(sslopt={"context": ctx}, ping_interval=20),
        daemon=True
    )
    t.start()
    return app


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    now    = time.time()
    w_end  = window_end(now)
    w_start = window_start(now)
    remaining = int(w_end - now)
    slug   = current_slug(now)

    print(f"\n{'═'*68}")
    print(f"  BET TIMING TEST")
    print(f"  Current window : {fmt(w_start)} → {fmt(w_end)}")
    print(f"  Time remaining : {remaining}s")
    print(f"  Slug           : {slug}")
    print(f"{'═'*68}\n")

    # If less than 2 minutes left, wait for the next window
    if remaining < 120:
        wait = remaining + 2
        print(f"  Less than 2 minutes left — waiting {wait}s for next window to start...")
        time.sleep(wait)
        now     = time.time()
        w_end   = window_end(now)
        w_start = window_start(now)
        remaining = int(w_end - now)
        slug    = current_slug(now)
        print(f"\n  New window: {fmt(w_start)} → {fmt(w_end)}")

    print("  Connecting to WS price feed...")
    ws_app = start_ws()
    time.sleep(3)  # let WS settle

    print(f"  Resolving market {slug}...")
    market = None
    for _ in range(15):
        try:
            market = resolve_market(slug)
            if market:
                break
        except Exception:
            pass
        time.sleep(1)

    if not market:
        print("  ERROR: Could not resolve market. Exiting.")
        return

    print(f"  Market: {market['title']}")
    print(f"  UP token  : {market['up_id'][:20]}...")
    print(f"  DOWN token: {market['down_id'][:20]}...\n")

    # ── Poll every second for last 2 minutes ─────────────────────────────────
    POLL_START_SECONDS_BEFORE_CLOSE = 120
    poll_start = w_end - POLL_START_SECONDS_BEFORE_CLOSE

    wait_until = poll_start - time.time()
    if wait_until > 0:
        print(f"  Waiting {int(wait_until)}s until T-{POLL_START_SECONDS_BEFORE_CLOSE}s mark...")
        print(f"  Polling will begin at {fmt(poll_start)}\n")
        time.sleep(wait_until)

    print(f"  {'─'*66}")
    print(f"  {'TIME':>8}  {'REM':>4}  {'BTC PRICE':>12}  {'UP ASK':>8}  {'UP ASKS':>7}  {'DOWN ASK':>9}  STATUS")
    print(f"  {'─'*66}")

    log = []
    last_up_ask_time   = None
    last_down_ask_time = None
    last_up_ask        = None
    last_down_ask      = None

    while True:
        now       = time.time()
        remaining = int(w_end - now)
        if remaining < -3:
            break

        ts_str = fmt(now)
        with _ws_lock:
            btc = _ws_price[0]

        up_ask,   n_up_asks,   up_bid,   _ = get_book_snapshot(market["up_id"])
        down_ask, n_down_asks, down_bid, _ = get_book_snapshot(market["down_id"])

        if up_ask   is not None: last_up_ask_time   = now; last_up_ask   = up_ask
        if down_ask is not None: last_down_ask_time = now; last_down_ask = down_ask

        status = "OPEN" if (up_ask or down_ask) else "⚠️  NO ASKS"
        if remaining <= 0:
            status = "🔴 WINDOW CLOSED"

        btc_str  = f"${btc:,.2f}" if btc else "  n/a   "
        up_str   = f"${up_ask:.4f}"   if up_ask   else "  NONE  "
        down_str = f"${down_ask:.4f}" if down_ask else "   NONE  "

        print(
            f"  {ts_str}  {remaining:>4}s  {btc_str:>12}  "
            f"{up_str:>8}  {n_up_asks:>7}  {down_str:>9}  {status}"
        )
        log.append({
            "ts": now, "remaining": remaining,
            "up_ask": up_ask, "down_ask": down_ask,
            "n_up_asks": n_up_asks, "n_down_asks": n_down_asks,
        })

        time.sleep(1)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n  {'═'*66}")
    print(f"  📊 BET TIMING RESULTS")
    print(f"  {'─'*66}")
    if last_up_ask_time:
        secs_before = int(w_end - last_up_ask_time)
        print(f"  🕐 Last UP ask seen   : {fmt(last_up_ask_time)}  "
              f"(T-{secs_before}s before close)  price={last_up_ask:.4f}")
    else:
        print(f"  🕐 Last UP ask seen   : (none seen)")

    if last_down_ask_time:
        secs_before = int(w_end - last_down_ask_time)
        print(f"  🕐 Last DOWN ask seen : {fmt(last_down_ask_time)}  "
              f"(T-{secs_before}s before close)  price={last_down_ask:.4f}")
    else:
        print(f"  🕐 Last DOWN ask seen : (none seen)")

    earliest_no_asks = next(
        (r for r in log if r["up_ask"] is None and r["down_ask"] is None), None
    )
    if earliest_no_asks:
        secs_before = int(w_end - earliest_no_asks["ts"])
        print(f"  ❌ Book went EMPTY at : {fmt(earliest_no_asks['ts'])}  "
              f"(T-{secs_before}s before close)")

    print(f"\n  💡 LIVE TRADING NOTE:")
    print(f"     The last second with asks = the last moment you can take liquidity.")
    print(f"     For a real order, subtract ~1-2s for Polygon tx confirmation.")
    print(f"     → Safe live cutoff ≈ T-{(int(w_end - last_up_ask_time) if last_up_ask_time else '?') + 2}s before close")
    print(f"  {'═'*66}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
