#!/usr/bin/env python3
"""
probe_close_timing.py — Probe market close timing + paper bet with P&L.

Behaviour:
  • If mid-window  → sleep silently until next window boundary, grab PTB from
                     the very first tick, then wake up for the final WAKE_UP_BEFORE
                     seconds of THAT window.
  • If at boundary → grab PTB immediately, sleep silently until WAKE_UP_BEFORE
                     seconds before close, then run the probe phase.

Probe phase (last WAKE_UP_BEFORE seconds):
  • Streams live Chainlink ticks vs PTB.
  • Hits the order book at each mark in PROBE_MARKS.
  • At BET_AT_MARK seconds before close, reads the order book and places a
    PAPER BET on whichever side has the higher ask (market favourite).
  • After the window closes, polls for resolution and prints P&L.

Usage:
    python probe_close_timing.py
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

# ── Config ──────────────────────────────────────────────────────────────────────
LIVE_WS_URL   = "wss://ws-live-data.polymarket.com/"
GAMMA_HOST    = "https://gamma-api.polymarket.com"
CLOB_HOST     = "https://clob.polymarket.com"
WINDOW_SECS   = 300          # 5-minute window

WAKE_UP_BEFORE      = 90    # seconds before close to start streaming/probing
STAKE_USD           = 1.00  # paper stake per trade

# Bet window: place bet at the FIRST probe within this range where
# the signal side still has liquidity. Both values in seconds before close.
BET_WINDOW_START    = 30    # earliest we'll bet (T-30s)
BET_WINDOW_END      = 5     # latest we'll bet  (T-5s)

# Minimum ask price for the dominant side to count as a confident signal.
# e.g. 0.65 means dominant side must be priced at $0.65+ (65% probability).
CONFIDENCE_THRESHOLD = 0.65

# Order-book probe marks (seconds before close)
PROBE_MARKS = [80, 70, 60, 50, 40, 35, 30, 25, 20, 18, 15, 12, 10, 8, 5, 3, 2, 1, 0]

SETTLE_POLL_INTERVAL = 5     # seconds between resolution checks
SETTLE_MAX_ATTEMPTS  = 60    # give up after 5 minutes


# ── SSL + WS headers ────────────────────────────────────────────────────────────
def make_ssl_ctx():
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
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}


# ── Time helpers ─────────────────────────────────────────────────────────────────
def win_start(ts=None):
    t = ts if ts is not None else time.time()
    return int(t // WINDOW_SECS) * WINDOW_SECS

def win_end(ts=None):
    return win_start(ts) + WINDOW_SECS

def slug_for(ts=None):
    return f"btc-updown-5m-{win_start(ts)}"

def fmt(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")

def fmt_win(start_ts):
    return f"{fmt(start_ts)} → {fmt(start_ts + WINDOW_SECS)}"


# ── WS feed ───────────────────────────────────────────────────────────────────────
class WSFeed:
    def __init__(self):
        self._price = None
        self._ts_ms = None
        self._lock  = threading.Lock()
        self._ready = threading.Event()

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
                self._price = p.get("value")
                self._ts_ms = p.get("timestamp")
                self._ready.set()

        app = websocket.WebSocketApp(
            LIVE_WS_URL, header=WS_HEADERS,
            on_open=on_open, on_message=on_message,
        )
        threading.Thread(
            target=lambda: app.run_forever(
                sslopt={"context": ssl_ctx}, ping_interval=20
            ),
            daemon=True,
        ).start()
        self._ready.wait(timeout=20)

    def latest(self):
        with self._lock:
            return (self._price, self._ts_ms) if self._price is not None else None

    def price_at_or_after(self, ts_sec):
        with self._lock:
            if self._ts_ms is None or self._price is None:
                return None
            if self._ts_ms >= ts_sec * 1000:
                return self._price, self._ts_ms
        return None


# ── Market / order book / resolution ─────────────────────────────────────────────
def resolve_market(slug, timeout=10):
    r = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=timeout)
    r.raise_for_status()
    events = r.json()
    if not events:
        return None
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
    }


def probe_book(token_id, timeout=2):
    """Return (best_ask or None, n_asks)."""
    try:
        r = requests.get(f"{CLOB_HOST}/book", params={"token_id": token_id}, timeout=timeout)
        r.raise_for_status()
        asks = r.json().get("asks", [])
        if not asks:
            return None, 0
        best = float(min(asks, key=lambda a: float(a["price"]))["price"])
        return best, len(asks)
    except Exception:
        return None, 0


def check_resolution(slug):
    """Returns (up_won: True/False/None, outcome_prices list)."""
    try:
        r = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=5)
        r.raise_for_status()
        events = r.json()
        if not events:
            return None, []
        mkt    = events[0]["markets"][0]
        prices = [float(p) for p in json.loads(mkt.get("outcomePrices") or "[]")]
        if prices and max(prices) >= 0.99:
            return prices[0] >= 0.99, prices
        return None, prices
    except Exception:
        return None, []


# ── Probe + paper bet phase ───────────────────────────────────────────────────────
def run_probe_phase(ws: WSFeed, ptb: float, w_end: int, market: dict):
    """
    Stream the last WAKE_UP_BEFORE seconds of a window, probe the order book at
    each PROBE_MARKS countdown.

    Signal logic:
      - After each probe where BOTH sides have asks AND the dominant side's ask
        meets CONFIDENCE_THRESHOLD, update last_clear_signal.
      - Within the bet window (BET_WINDOW_START → BET_WINDOW_END seconds before
        close), place the bet on the FIRST probe where the signal side still has
        liquidity. Skip if the correct side has dried up.

    Returns (probe_results, decided_side, entry_price, last_price).
    """
    last_tick_ts       = None
    last_price         = ptb
    tick_count         = 0
    probes_done        = set()
    results            = []
    decided_side       = None
    entry_price        = None

    # ── Signal tracking state ────────────────────────────────────────────────
    last_clear_signal      = None   # "UP" or "DOWN"
    last_clear_up_ask      = None   # ask price when signal was last updated
    last_clear_down_ask    = None
    last_clear_mark        = None   # which probe mark set it
    prev_clear_signal      = None   # to detect flips
    signal_flip_at_mark    = None   # mark at which the signal flipped

    print(f"\n  Streaming last {WAKE_UP_BEFORE}s — probes at: {PROBE_MARKS}s before close")
    print(f"  Bet window: T-{BET_WINDOW_START}s → T-{BET_WINDOW_END}s  "
          f"| Confidence threshold: {CONFIDENCE_THRESHOLD:.0%}")
    print(f"  {'─'*72}")

    while True:
        now       = time.time()
        remaining = w_end - now

        if remaining <= -3:
            break

        # New tick?
        ws_data = ws.latest()
        if ws_data:
            price, ts_ms = ws_data
            if ts_ms != last_tick_ts:
                last_tick_ts = ts_ms
                last_price   = price
                tick_count  += 1
                diff  = price - ptb
                arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "─")
                print(
                    f"  tick #{tick_count:>3}  {fmt(ts_ms/1000)}  "
                    f"${price:>10,.2f}  {arrow} {diff:>+7.2f}  "
                    f"ptb=${ptb:,.2f}  {int(remaining):>3}s left"
                )

        # Fire probes at each countdown mark
        for mark in PROBE_MARKS:
            if mark in probes_done:
                continue
            if remaining <= mark:
                probes_done.add(mark)
                up_ask,   n_up   = probe_book(market["up_id"])
                down_ask, n_down = probe_book(market["down_id"])
                has_liq = (up_ask is not None or down_ask is not None)
                status  = "✅ OPEN" if has_liq else "❌ CLOSED"
                up_str   = f"${up_ask:.4f}"   if up_ask   else "  NONE"
                down_str = f"${down_ask:.4f}" if down_ask else "  NONE"

                # ── Update last clear signal (both sides must be visible) ───
                signal_tag = ""
                if up_ask is not None and down_ask is not None:
                    dominant      = max(up_ask, down_ask)
                    new_signal    = "UP" if up_ask > down_ask else "DOWN"
                    if dominant >= CONFIDENCE_THRESHOLD:
                        prev_clear_signal = last_clear_signal
                        last_clear_signal = new_signal
                        last_clear_up_ask   = up_ask
                        last_clear_down_ask = down_ask
                        last_clear_mark     = mark
                        if prev_clear_signal and prev_clear_signal != new_signal:
                            signal_flip_at_mark = mark
                            signal_tag = f"  ⚡ SIGNAL FLIPPED → {new_signal}"
                        else:
                            signal_tag = f"  📶 signal={new_signal}"
                    else:
                        signal_tag = f"  ⚠️  low confidence ({dominant:.2f} < {CONFIDENCE_THRESHOLD:.2f})"
                elif up_ask is None and down_ask is None:
                    signal_tag = "  (both gone)"

                print(
                    f"\n  ► PROBE T-{mark:>2}s  {fmt(now)}  "
                    f"UP={up_str} ({n_up})  DOWN={down_str} ({n_down})  "
                    f"BTC=${last_price:,.2f}  → {status}{signal_tag}"
                )
                results.append({
                    "mark": mark, "ts": now, "remaining": remaining,
                    "up_ask": up_ask, "n_up": n_up,
                    "down_ask": down_ask, "n_down": n_down,
                    "has_liquidity": has_liq,
                    "signal": last_clear_signal,
                })

                # ── Bet logic: fire within bet window ────────────────────────
                in_bet_window = (BET_WINDOW_END <= mark <= BET_WINDOW_START)
                if in_bet_window and decided_side is None:
                    if last_clear_signal is None:
                        print(f"  ⏭️  T-{mark}s: No confident signal yet — waiting...")
                    else:
                        # Check if the signal side still has liquidity right now
                        sig_ask = up_ask if last_clear_signal == "UP" else down_ask
                        if sig_ask is not None:
                            decided_side = last_clear_signal
                            entry_price  = sig_ask
                            payout = STAKE_USD / entry_price
                            profit = payout - STAKE_USD
                            flip_warn = (
                                f"  ⚡ Note: signal flipped at T-{signal_flip_at_mark}s"
                                if signal_flip_at_mark else ""
                            )
                            print(
                                f"\n  ┌──────────────────────────────────────────────────────────┐"
                                f"\n  │  🎯 PAPER BET  →  {decided_side:<4}  @ ${entry_price:.4f}  (T-{mark}s)           │"
                                f"\n  │  Signal from T-{last_clear_mark}s: UP=${last_clear_up_ask:.4f}  "
                                f"DOWN=${last_clear_down_ask:.4f}           │"
                                f"\n  │  Stake: ${STAKE_USD:.2f}   Payout: ${payout:.4f}  Profit: +${profit:.4f}           │"
                                f"\n  └──────────────────────────────────────────────────────────┘"
                                + (f"\n  {flip_warn}" if flip_warn else "")
                            )
                        else:
                            # Signal side has no liquidity — don't bet
                            print(
                                f"\n  🚫 T-{mark}s: Signal={last_clear_signal} but {last_clear_signal} "
                                f"side has no asks — SKIP BET (correct side dried up)"
                            )

        time.sleep(0.1)

    # ── Print signal history after loop ─────────────────────────────────────
    print(f"\n  📶 Final signal: {last_clear_signal}  "
          f"(last updated at T-{last_clear_mark}s  "
          f"UP=${last_clear_up_ask:.4f}  DOWN=${last_clear_down_ask:.4f})"
          if last_clear_signal else "\n  📶 No confident signal captured.")
    if signal_flip_at_mark:
        print(f"  ⚡ Signal flipped at T-{signal_flip_at_mark}s  "
              f"({prev_clear_signal} → {last_clear_signal})")

    return results, decided_side, entry_price, last_price


# ── Settlement ────────────────────────────────────────────────────────────────────
def settle(slug, decided_side, entry_price):
    print(f"\n  ⏳ Polling for market resolution ({slug})...")
    for attempt in range(1, SETTLE_MAX_ATTEMPTS + 1):
        time.sleep(SETTLE_POLL_INTERVAL)
        up_won, prices = check_resolution(slug)
        print(f"  [settle {attempt}]  prices={[f'{p:.4f}' for p in prices]}")
        if up_won is not None:
            actual = "UP ▲" if up_won else "DOWN ▼"
            won = (decided_side == "UP" and up_won) or (decided_side == "DOWN" and not up_won)
            pnl = STAKE_USD * (1 / entry_price - 1) if won else -STAKE_USD
            print(f"\n  ════════════════════════════════════════════════")
            print(f"  🏆 RESULT     : {'WIN  ✅' if won else 'LOSS ❌'}")
            print(f"  📌 We bet     : {decided_side}")
            print(f"  🎯 Outcome    : {actual}")
            print(f"  💰 P&L        : ${pnl:>+.4f}  (stake ${STAKE_USD:.2f})")
            print(f"  ════════════════════════════════════════════════\n")
            return
    print("  ⚠️  Market did not resolve within the wait period.")


# ── Summary table ─────────────────────────────────────────────────────────────────
def print_summary(results, w_start, w_end, ptb, last_price, decided_side, entry_price):
    net = last_price - ptb
    direction = "UP ▲" if net > 0 else "DOWN ▼"

    print(f"\n  {'═'*72}")
    print(f"  ⏰ WINDOW CLOSED : {fmt_win(w_start)}")
    print(f"  📌 Price to Beat  : ${ptb:,.2f}")
    print(f"  🏁 Final Price    : ${last_price:,.2f}  (next window's PTB)")
    print(f"  📊 Net move       : {net:>+.2f}   →  {direction}")
    if decided_side:
        signal_correct = (
            (decided_side == "UP"   and net > 0) or
            (decided_side == "DOWN" and net < 0)
        )
        print(f"  🎯 Our bet        : {decided_side} @ ${entry_price:.4f}  "
              f"→ {'Signal was CORRECT ✅' if signal_correct else 'Signal was WRONG ❌'}")
    print(f"  {'─'*72}")
    print(f"  {'T-MARK':>8}  {'TIME':>8}  {'UP ASK':>8}  {'DOWN ASK':>9}  STATUS")
    print(f"  {'─'*72}")

    last_open_mark    = None
    first_closed_mark = None
    for r in results:
        up_str   = f"${r['up_ask']:.4f}"   if r["up_ask"]   else "  NONE  "
        down_str = f"${r['down_ask']:.4f}" if r["down_ask"] else "   NONE  "
        status   = "✅ OPEN" if r["has_liquidity"] else "❌ CLOSED"
        bet_tag  = "  ← BET" if r["mark"] == BET_AT_MARK else ""
        print(f"  T-{r['mark']:>4}s  {fmt(r['ts']):>8}  {up_str:>8}  {down_str:>9}  {status}{bet_tag}")
        if r["has_liquidity"]:
            last_open_mark = r["mark"]
        elif first_closed_mark is None:
            first_closed_mark = r["mark"]

    print(f"  {'═'*72}")
    if last_open_mark is not None:
        print(f"\n  ✅ LAST open moment  : T-{last_open_mark}s before close")
    if first_closed_mark is not None:
        print(f"  ❌ FIRST empty moment: T-{first_closed_mark}s before close")
    if last_open_mark is not None:
        print(f"  💡 Safe cutoff       : T-{last_open_mark + 2}s  (with 2s buffer)")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────────
def main():
    now       = time.time()
    w_s       = win_start(now)
    w_e       = win_end(now)
    secs_into = now - w_s
    remaining = w_e - now

    print(f"\n{'═'*72}")
    print(f"  PROBE CLOSE TIMING  +  PAPER BET")
    print(f"  Current time   : {fmt(now)}")
    print(f"  Current window : {fmt_win(w_s)}")
    print(f"  Into window    : {int(secs_into)}s  |  Remaining: {int(remaining)}s")
    print(f"  Stake          : ${STAKE_USD:.2f}  |  Bet window: T-{BET_WINDOW_START}s → T-{BET_WINDOW_END}s")
    print(f"{'═'*72}\n")

    print("  Connecting to Polymarket WS feed...")
    ws = WSFeed()
    ws.start()

    # Confirm connection
    for _ in range(40):
        if ws.latest():
            break
        time.sleep(0.5)
    tick = ws.latest()
    if not tick:
        print("  ❌ No WS data — check connection. Exiting.")
        sys.exit(1)
    btc_now, _ = tick
    print(f"  ✅ WS connected — BTC/USD: ${btc_now:,.2f}\n")

    # ── Determine PTB and target window ──────────────────────────────────────────
    if secs_into > 10:
        # Mid-window: sleep until the NEXT boundary, then grab PTB
        sleep_secs = w_e - time.time() + 0.5
        print(f"  ⚠️  Mid-window ({int(secs_into)}s in, {int(remaining)}s remaining).")
        print(f"  ⏳ Sleeping {int(sleep_secs)}s until next boundary ({fmt(w_e)})...\n")
        time.sleep(max(0, sleep_secs))

        now = time.time()
        w_s = win_start(now)
        w_e = w_s + WINDOW_SECS
    # else: we're right at the boundary — use current w_s / w_e

    slug = slug_for(w_s)
    print(f"  📡 Window: {fmt_win(w_s)}")
    print(f"  Waiting for first tick (Price to Beat)...")

    ptb      = None
    deadline = time.time() + 30
    while time.time() < deadline:
        result = ws.price_at_or_after(w_s)
        if result:
            ptb, ptb_ts_ms = result
            lag = int(ptb_ts_ms / 1000 - w_s)
            print(f"  📌 PRICE TO BEAT : ${ptb:,.2f}  (+{lag}s after boundary)\n")
            break
        time.sleep(0.1)

    if ptb is None:
        print("  ❌ Could not capture PTB in 30s — exiting.")
        sys.exit(1)

    # ── Resolve market tokens ─────────────────────────────────────────────────────
    print(f"  🔍 Resolving market {slug}...")
    market = None
    for _ in range(20):
        try:
            market = resolve_market(slug)
            if market:
                break
        except Exception:
            pass
        time.sleep(2)

    if not market:
        print("  ❌ Could not resolve market — exiting.")
        sys.exit(1)
    print(f"  📋 {market['title']}\n")

    # ── Sleep silently until WAKE_UP_BEFORE seconds before close ─────────────────
    wake_at   = w_e - WAKE_UP_BEFORE
    wait_secs = wake_at - time.time()
    if wait_secs > 0:
        print(f"  ⏳ Sleeping {int(wait_secs)}s — will wake up at T-{WAKE_UP_BEFORE}s ({fmt(wake_at)})...\n")
        time.sleep(wait_secs)

    # ── Run the probe + bet phase ─────────────────────────────────────────────────
    results, decided_side, entry_price, last_price = run_probe_phase(
        ws, ptb, w_e, market
    )

    # ── Window close summary ──────────────────────────────────────────────────────
    print_summary(results, w_s, w_e, ptb, last_price, decided_side, entry_price)

    # ── Settle ────────────────────────────────────────────────────────────────────
    if decided_side and entry_price:
        settle(slug, decided_side, entry_price)
    else:
        print("  ℹ️  No bet was placed — nothing to settle.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Stopped by user.")
