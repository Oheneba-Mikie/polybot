#!/usr/bin/env python3
"""
smartbot.py — BTC 5-min Up/Down Polymarket bot (paper trading)

Strategy (confirmed from live testing):
  1. Wait for window boundary (xx:x0:00 or xx:x5:00)
  2. Capture Price to Beat = first WS tick at window open
  3. Stream ticks + poll order book every second from T-120s
  4. At T-20s: read order book — bet on the side the MARKET is pricing as favorite
     (highest ask price = market thinks it's most likely to win)
  5. Show window close summary + settlement

Run:
    python smartbot.py
    python smartbot.py --cycles 3     # run N windows then exit
    python smartbot.py --dry-run      # observe only, no bet placed
"""

import argparse
import json
import os
import ssl
import sys
import time
import datetime
import threading
import requests
import websocket

# ── Config ────────────────────────────────────────────────────────────────────
WINDOW_SECONDS           = 300        # 5-minute windows
BET_SECONDS_BEFORE_CLOSE = 20         # place bet at T-20s (last confirmed safe moment)
ORDER_BOOK_START_BEFORE  = 120        # start polling order book at T-120s
SETTLE_POLL_INTERVAL     = 5          # check resolution every 5s
SETTLE_MAX_ATTEMPTS      = 60         # wait up to 5 minutes for resolution
STAKE_USD                = 1.00       # paper stake per trade

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"
LIVE_WS_URL = "wss://ws-live-data.polymarket.com/"


# ── SSL + headers ─────────────────────────────────────────────────────────────
def _make_ssl_context():
    ctx = ssl.create_default_context()
    for p in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(p):
            ctx.load_verify_locations(p)
            break
    return ctx

WS_SSL_CTX = _make_ssl_context()
WS_HEADERS = {
    "Origin": "https://polymarket.com",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}


# ── Time helpers ──────────────────────────────────────────────────────────────
def window_start(ts=None):
    t = ts or time.time()
    return int(t // WINDOW_SECONDS) * WINDOW_SECONDS

def window_end(ts=None):
    return window_start(ts) + WINDOW_SECONDS

def current_slug(ts=None):
    return f"btc-updown-5m-{window_start(ts)}"

def fmt(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")

def fmt_window(start_ts):
    return f"{fmt(start_ts)} → {fmt(start_ts + WINDOW_SECONDS)}"


# ── Live WS price feed ────────────────────────────────────────────────────────
class WSFeed:
    def __init__(self):
        self._price     = None
        self._ts_ms     = None
        self._lock      = threading.Lock()
        self._connected = threading.Event()
        self._app       = None

    def start(self):
        def on_open(ws):
            ws.send(json.dumps({
                "action": "subscribe",
                "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}]
            }))
            self._connected.set()

        def on_message(ws, raw):
            if not raw: return
            try:
                msg = json.loads(raw)
            except: return
            if msg.get("topic") != "crypto_prices_chainlink": return
            p = msg.get("payload", {})
            if p.get("symbol") != "btc/usd": return
            with self._lock:
                self._price  = p.get("value")
                self._ts_ms  = p.get("timestamp")

        self._app = websocket.WebSocketApp(
            LIVE_WS_URL, header=WS_HEADERS,
            on_open=on_open, on_message=on_message,
        )
        t = threading.Thread(
            target=lambda: self._app.run_forever(
                sslopt={"context": WS_SSL_CTX}, ping_interval=20
            ), daemon=True
        )
        t.start()
        self._connected.wait(timeout=20)

    def latest(self):
        with self._lock:
            if self._price is None: return None
            return self._price, self._ts_ms

    def price_at_or_after(self, ts_sec):
        """Return (price, ts_ms) if the latest tick is at or after ts_sec."""
        with self._lock:
            if self._ts_ms is None or self._price is None: return None
            if self._ts_ms >= ts_sec * 1000:
                return self._price, self._ts_ms
        return None


# ── Market resolution ─────────────────────────────────────────────────────────
def resolve_market(slug, timeout=10):
    resp = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=timeout)
    resp.raise_for_status()
    events = resp.json()
    if not events: return None
    mkt = events[0]["markets"][0]
    token_ids = json.loads(mkt.get("clobTokenIds") or "[]")
    outcomes  = [str(o).lower() for o in json.loads(mkt.get("outcomes") or "[]")]
    up_id = down_id = None
    for i, o in enumerate(outcomes):
        if o in ("up", "yes"):    up_id   = token_ids[i]
        elif o in ("down", "no"): down_id = token_ids[i]
    if not up_id:   up_id   = token_ids[0]
    if not down_id: down_id = token_ids[1]
    return {
        "slug": slug,
        "title": mkt.get("question", slug),
        "up_id": up_id,
        "down_id": down_id,
        "condition_id": mkt.get("conditionId", ""),
    }


# ── Order book ────────────────────────────────────────────────────────────────
def get_book(token_id, timeout=3):
    """Returns (best_ask, n_asks) or (None, 0) on error/empty."""
    try:
        r = requests.get(f"{CLOB_HOST}/book", params={"token_id": token_id}, timeout=timeout)
        r.raise_for_status()
        asks = r.json().get("asks", [])
        if not asks: return None, 0
        best = float(min(asks, key=lambda a: float(a["price"]))["price"])
        return best, len(asks)
    except:
        return None, 0


# ── Resolution check ──────────────────────────────────────────────────────────
def check_resolution(slug):
    """Returns (up_won: bool|None, outcome_prices)."""
    try:
        r = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=5)
        r.raise_for_status()
        events = r.json()
        if not events: return None, []
        mkt = events[0]["markets"][0]
        prices = json.loads(mkt.get("outcomePrices") or "[]")
        prices_f = [float(p) for p in prices]
        if prices_f and max(prices_f) >= 0.99:
            up_won = prices_f[0] >= 0.99
            return up_won, prices_f
        return None, prices_f
    except:
        return None, []


# ── Main cycle ────────────────────────────────────────────────────────────────
def run_cycle(ws: WSFeed, cycle_num: int, dry_run: bool) -> bool:
    """Returns True if completed successfully."""
    now        = time.time()
    w_start    = window_start(now)
    w_end      = window_end(now)
    remaining  = w_end - now
    slug       = current_slug(now)

    print(f"\n{'═'*68}")
    print(f"  CYCLE #{cycle_num}  |  {fmt_window(w_start)}")
    print(f"{'═'*68}")

    # ── Step 1: Wait for window boundary if we're mid-window ─────────────────
    secs_into = now - w_start
    if secs_into > 5:
        wait = w_end - now + 0.5
        print(f"  ⏳ Mid-window ({int(secs_into)}s in) — waiting {int(wait)}s for next window...")
        time.sleep(wait)
        now     = time.time()
        w_start = window_start(now)
        w_end   = window_end(now)
        slug    = current_slug(now)
        print(f"  ✅ New window: {fmt_window(w_start)}")

    # ── Step 2: Capture Price to Beat (first tick at window open) ────────────
    print(f"  📡 Waiting for Price to Beat (first tick at {fmt(w_start)})...")
    ptb       = None
    ptb_ts    = None
    deadline  = time.time() + 60
    while time.time() < deadline:
        result = ws.price_at_or_after(w_start)
        if result:
            ptb, ptb_ts_ms = result
            ptb_ts = ptb_ts_ms / 1000
            lag = int(ptb_ts - w_start)
            print(f"  📌 PRICE TO BEAT : ${ptb:,.2f}  (captured +{lag}s after window open)")
            break
        time.sleep(0.2)

    if ptb is None:
        print("  ❌ Could not get Price to Beat — skipping this cycle")
        return False

    # ── Step 3: Resolve market ────────────────────────────────────────────────
    print(f"  🔍 Resolving market {slug}...")
    market = None
    for _ in range(20):
        try:
            market = resolve_market(slug)
            if market: break
        except: pass
        time.sleep(2)

    if not market:
        print("  ❌ Could not resolve market — skipping")
        return False

    print(f"  📋 {market['title']}")

    # ── Step 4: Stream ticks + poll order book in last 2 minutes ─────────────
    last_tick_ts  = None
    last_price    = ptb
    tick_count    = 0
    book_polling  = False
    decided_side  = None
    entry_price   = None

    print(f"\n  Streaming ticks until T-{ORDER_BOOK_START_BEFORE}s, then order book polling starts...")
    print(f"  {'─'*64}")

    while True:
        now       = time.time()
        remaining = w_end - now
        if remaining <= -2:
            break

        # Print new WS ticks
        ws_latest = ws.latest()
        if ws_latest:
            price, ts_ms = ws_latest
            if ts_ms != last_tick_ts:
                last_tick_ts = ts_ms
                last_price   = price
                tick_count  += 1
                diff  = price - ptb
                arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "─")
                tick_t = fmt(ts_ms / 1000)

                # Compact tick line (suppress during order book phase to reduce noise)
                if not book_polling:
                    print(
                        f"  tick #{tick_count:>3}  {tick_t}  "
                        f"${price:>10,.2f}  {arrow} {diff:>+7.2f}  "
                        f"ptb=${ptb:,.2f}  {int(remaining):>3}s left"
                    )

        # Enter order book polling phase at T-120s
        if remaining <= ORDER_BOOK_START_BEFORE and not book_polling:
            book_polling = True
            print(f"\n  {'─'*64}")
            print(f"  📊 ORDER BOOK PHASE — polling every second from T-{int(remaining):.0f}s")
            print(f"  {'UP ASK':>10}  {'UP #':>5}  {'DOWN ASK':>10}  {'DOWN #':>6}  {'SIGNAL':>12}  REM")
            print(f"  {'─'*64}")

        if book_polling:
            up_ask,   n_up   = get_book(market["up_id"])
            down_ask, n_down = get_book(market["down_id"])

            # Determine market signal
            if up_ask and down_ask:
                signal = "UP 📈" if up_ask > down_ask else "DOWN 📉"
            elif up_ask:
                signal = "UP 📈"
            elif down_ask:
                signal = "DOWN 📉"
            else:
                signal = "—"

            up_str   = f"${up_ask:.4f}"   if up_ask   else "  NONE"
            down_str = f"${down_ask:.4f}" if down_ask else "  NONE"
            btc_str  = f"${last_price:,.2f}" if last_price else "  n/a  "

            print(
                f"  {up_str:>10}  {n_up:>5}  {down_str:>10}  {n_down:>6}  "
                f"{signal:>12}  T-{int(remaining):>3}s   BTC={btc_str}"
            )

            # Place bet at T-20s
            if remaining <= BET_SECONDS_BEFORE_CLOSE and decided_side is None and not dry_run:
                if up_ask and down_ask:
                    if up_ask > down_ask:
                        decided_side = "UP"
                        entry_price  = up_ask
                    else:
                        decided_side = "DOWN"
                        entry_price  = down_ask
                elif up_ask:
                    decided_side = "UP";   entry_price = up_ask
                elif down_ask:
                    decided_side = "DOWN"; entry_price = down_ask

                if decided_side:
                    print(f"\n  >>> 🎯 [PAPER BET] BUY {decided_side}  stake=${STAKE_USD:.2f}"
                          f"  entry={entry_price:.4f}  at T-{int(remaining):.0f}s")
                elif dry_run:
                    print(f"\n  >>> 👁️  [DRY RUN] Would bet {signal} at T-{int(remaining):.0f}s")

            time.sleep(1)
        else:
            time.sleep(0.1)

    # ── Window close summary ──────────────────────────────────────────────────
    net_move   = last_price - ptb
    actual_dir = "UP ▲" if net_move > 0 else "DOWN ▼"

    print(f"\n  {'═'*64}")
    print(f"  ⏰ WINDOW CLOSED  {fmt_window(w_start)}")
    print(f"  📌 Price to Beat  (window open)  : ${ptb:>10,.2f}")
    print(f"  🏁 Final Price    (window close)  : ${last_price:>10,.2f}  ← next window's PtB")
    print(f"  📊 Net move                       : {net_move:>+10.2f}")
    print(f"  🎯 Actual result                  : {actual_dir}")
    if decided_side:
        correct = "✅ CORRECT" if (
            (decided_side == "UP"   and net_move > 0) or
            (decided_side == "DOWN" and net_move < 0)
        ) else "❌ WRONG"
        print(f"  🎰 Bot bet                        : {decided_side} @ {entry_price:.4f}  {correct}")
    else:
        print(f"  🎰 Bot bet                        : {'DRY RUN' if dry_run else 'NO BET (no liquidity)'}")
    print(f"  🔢 Ticks seen                     : {tick_count}")
    print(f"  {'═'*64}")

    # ── Settlement ────────────────────────────────────────────────────────────
    if decided_side and not dry_run:
        print(f"\n  ⏳ Waiting for market resolution...")
        for attempt in range(1, SETTLE_MAX_ATTEMPTS + 1):
            time.sleep(SETTLE_POLL_INTERVAL)
            up_won, prices = check_resolution(slug)
            print(f"  [settle {attempt}/{SETTLE_MAX_ATTEMPTS}] prices={prices}")
            if up_won is not None:
                won = (decided_side == "UP" and up_won) or (decided_side == "DOWN" and not up_won)
                pnl = STAKE_USD * (1 / entry_price - 1) if won else -STAKE_USD
                print(f"\n  🏆 RESULT: {'WIN' if won else 'LOSS'}  P&L: ${pnl:+.4f}")
                return True

        print("  ⚠️  Market did not resolve in time — continuing")

    return True


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Smartbot — market-direction BTC Up/Down bot")
    parser.add_argument("--cycles",  type=int,  default=None, help="number of cycles to run (default: forever)")
    parser.add_argument("--dry-run", action="store_true",     help="observe only, do not place bets")
    args = parser.parse_args()

    print("PAPER TRADING ONLY — no real orders will ever be placed.")
    if args.dry_run:
        print("DRY RUN mode — will observe but not bet.\n")

    print("Connecting to Polymarket live WS feed...")
    ws = WSFeed()
    ws.start()

    # Wait for first tick
    for _ in range(60):
        if ws.latest(): break
        time.sleep(0.5)
    tick = ws.latest()
    if tick:
        price, _ = tick
        print(f"  ✅ Connected — BTC/USD: ${price:,.2f}\n")
    else:
        print("  ❌ Could not get WS price — check connection")
        return

    cycle_num = 0
    while True:
        cycle_num += 1
        if args.cycles and cycle_num > args.cycles:
            print(f"\n✅ Completed {args.cycles} cycle(s). Done.")
            break
        try:
            run_cycle(ws, cycle_num, dry_run=args.dry_run)
        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except Exception as e:
            print(f"\n⚠️  Cycle error: {e} — retrying next window")
            time.sleep(10)


if __name__ == "__main__":
    main()
