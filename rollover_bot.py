#!/usr/bin/env python3
"""
rollover_bot.py — BTC 5-min Polymarket trading bot using compounding & 50% backing reserve.

Strategy:
  1. Starts with an active stake (default $1) and a backing reserve (default $9).
  2. If starting mid-window, sleeps silently until the next boundary to ensure clean PTB.
  3. Captures Price to Beat (first Chainlink tick at boundary).
  4. Resolves the token IDs for the current market slug.
  5. Sleeps silently until T-90s before close.
  6. Streams ticks and probes the order book at each countdown mark.
  7. Tracks last_clear_signal when dominant side confidence >= 65%.
  8. Between T-30s and T-5s: places a paper bet on the first opportunity where the
     correct side is open.
  9. After close, waits for resolution:
     - Win  -> Profit is split 50/50: half added to stake, half to backing reserve.
     - Loss -> Current stake is lost. Staked is reset to $1 from backing reserve.
               If backing has less than $1, the bot halts due to lack of capital.
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

# ── Config ──────────────────────────────────────────────────────────────────────
LIVE_WS_URL   = "wss://ws-live-data.polymarket.com/"
GAMMA_HOST    = "https://gamma-api.polymarket.com"
CLOB_HOST     = "https://clob.polymarket.com"
WINDOW_SECS   = 300          # 5-minute window

WAKE_UP_BEFORE = 90          # seconds before close to start streaming/probing
BET_WINDOW_START = 30        # earliest we'll bet (T-30s)
BET_WINDOW_END = 5           # latest we'll bet (T-5s)
CONFIDENCE_THRESHOLD = 0.65  # dominant ask must be >= $0.65 to establish signal

PROBE_MARKS = [80, 70, 60, 50, 40, 35, 30, 25, 20, 18, 15, 12, 10, 8, 5, 3, 2, 1, 0]

SETTLE_POLL_INTERVAL = 5     # seconds between resolution checks
SETTLE_MAX_ATTEMPTS  = 60    # give up after 5 minutes


# ── SSL Context Setup ───────────────────────────────────────────────────────────
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
        self._app   = None

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

        self._app = websocket.WebSocketApp(
            LIVE_WS_URL, header=WS_HEADERS,
            on_open=on_open, on_message=on_message,
        )
        threading.Thread(
            target=lambda: self._app.run_forever(
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


# ── State Class ──────────────────────────────────────────────────────────────────
class BotState:
    def __init__(self, start_stake, start_backing):
        self.stake = start_stake
        self.backing = start_backing
        self.wins = 0
        self.losses = 0
        self.initial_total = start_stake + start_backing

    def total_bankroll(self):
        return self.stake + self.backing

    def net_pnl(self):
        return self.total_bankroll() - self.initial_total

    def win_rate(self):
        total = self.wins + self.losses
        return (self.wins / total) * 100 if total > 0 else 0.0

    def print_dashboard(self):
        total_pnl = self.net_pnl()
        sign = "+" if total_pnl >= 0 else ""
        total_bets = self.wins + self.losses
        
        print(f"\n  ┌──────────────────────────────────────────────────────────┐")
        print(f"  │  📊 ROLLOVER BOT DASHBOARD                              │")
        print(f"  ├──────────────────────────────────────────────────────────┤")
        print(f"  │  Active Stake     :  ${self.stake:<10,.2f}                            │")
        print(f"  │  Reserve Backing  :  ${self.backing:<10,.2f}                            │")
        print(f"  │  Total Bankroll   :  ${self.total_bankroll():<10,.2f}                            │")
        print(f"  │  Net Profit/Loss  :  {sign}${total_pnl:<10,.2f}                            │")
        print(f"  ├──────────────────────────────────────────────────────────┤")
        print(f"  │  Record           :  {self.wins:>3} Wins  |  {self.losses:>3} Losses  ({self.win_rate():.1f}% rate)   │")
        print(f"  └──────────────────────────────────────────────────────────┘\n")


# ── Cycle Execution ──────────────────────────────────────────────────────────────
def run_cycle(ws: WSFeed, state: BotState, cycle_num: int):
    now       = time.time()
    w_s       = win_start(now)
    w_e       = win_end(now)
    secs_into = now - w_s
    remaining = w_e - now

    print(f"\n{'═'*72}")
    print(f"  CYCLE #{cycle_num}  |  {fmt_win(w_s)}")
    print(f"{'═'*72}\n")

    # ── Step 1: Sleep silently if mid-window to wait for boundary ────────────
    if secs_into > 10:
        sleep_secs = w_e - time.time() + 0.5
        print(f"  ⚠️  Starting mid-window ({int(secs_into)}s into current window).")
        print(f"  ⏳ Sleeping silently {int(sleep_secs)}s until next boundary ({fmt(w_e)})...")
        time.sleep(max(0, sleep_secs))

        now = time.time()
        w_s = win_start(now)
        w_e = w_s + WINDOW_SECS

    slug = slug_for(w_s)

    # ── Step 2: Grab Price to Beat ───────────────────────────────────────────
    print(f"  📡 Window active: {fmt_win(w_s)}")
    print(f"  Waiting for first tick (Price to Beat)...")
    ptb = None
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
        print("  ❌ Could not capture PTB within 30s — skipping this cycle.")
        return

    # ── Step 3: Resolve Market Tokens ────────────────────────────────────────
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
        print("  ❌ Could not resolve market — skipping this cycle.")
        return
    print(f"  📋 {market['title']}\n")

    # ── Step 4: Sleep until T-90s ────────────────────────────────────────────
    wake_at = w_e - WAKE_UP_BEFORE
    wait_secs = wake_at - time.time()
    if wait_secs > 0:
        print(f"  ⏳ Sleeping silently {int(wait_secs)}s — waking up at T-{WAKE_UP_BEFORE}s ({fmt(wake_at)})...")
        time.sleep(wait_secs)

    # ── Step 5: Active Stream / Probe / Bet Phase ────────────────────────────
    last_tick_ts       = None
    last_price         = ptb
    tick_count         = 0
    probes_done        = set()
    decided_side       = None
    entry_price        = None

    last_clear_signal      = None
    last_clear_up_ask      = None
    last_clear_down_ask    = None
    last_clear_mark        = None
    prev_clear_signal      = None
    signal_flip_at_mark    = None

    print(f"\n  Streaming last {WAKE_UP_BEFORE}s — probes at: {PROBE_MARKS}s before close")
    print(f"  Bet window: T-{BET_WINDOW_START}s → T-{BET_WINDOW_END}s")
    print(f"  Active Stake for this bet: ${state.stake:.2f}")
    print(f"  {'─'*72}")

    while True:
        now       = time.time()
        remaining = w_e - now

        if remaining <= -3:
            break

        ws_data = ws.latest()
        if ws_data:
            price, ts_ms = ws_data
            if ts_ms != last_tick_ts:
                last_tick_ts = ts_ms
                last_price   = price
                tick_count  += 1
                diff  = price - ptb
                arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "─")
                # Suppress printing tick lines during the last critical 5s
                if remaining > 5:
                    print(
                        f"  tick #{tick_count:>3}  {fmt(ts_ms/1000)}  "
                        f"${price:>10,.2f}  {arrow} {diff:>+7.2f}  "
                        f"ptb=${ptb:,.2f}  {int(remaining):>3}s left"
                    )

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

                signal_tag = ""
                if up_ask is not None and down_ask is not None:
                    dominant = max(up_ask, down_ask)
                    new_signal = "UP" if up_ask > down_ask else "DOWN"
                    if dominant >= CONFIDENCE_THRESHOLD:
                        prev_clear_signal = last_clear_signal
                        last_clear_signal = new_signal
                        last_clear_up_ask = up_ask
                        last_clear_down_ask = down_ask
                        last_clear_mark = mark
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

                # Bet trigger logic
                in_bet_window = (BET_WINDOW_END <= mark <= BET_WINDOW_START)
                if in_bet_window and decided_side is None:
                    if last_clear_signal is None:
                        print(f"  ⏭️  T-{mark}s: No confident signal yet — waiting...")
                    else:
                        sig_ask = up_ask if last_clear_signal == "UP" else down_ask
                        if sig_ask is not None:
                            decided_side = last_clear_signal
                            entry_price  = sig_ask
                            payout = state.stake / entry_price
                            profit = payout - state.stake
                            flip_warn = f"  ⚡ Note: signal flipped at T-{signal_flip_at_mark}s" if signal_flip_at_mark else ""
                            print(
                                f"\n  ┌──────────────────────────────────────────────────────────┐"
                                f"\n  │  🎯 PAPER BET  →  {decided_side:<4}  @ ${entry_price:.4f}  (T-{mark}s)           │"
                                f"\n  │  Signal from T-{last_clear_mark}s: UP=${last_clear_up_ask:.4f}  "
                                f"DOWN=${last_clear_down_ask:.4f}           │"
                                f"\n  │  Stake: ${state.stake:.2f}   Payout: ${payout:.4f}  Profit: +${profit:.4f}           │"
                                f"\n  └──────────────────────────────────────────────────────────┘"
                                + (f"\n  {flip_warn}" if flip_warn else "")
                            )
                        else:
                            print(
                                f"\n  🚫 T-{mark}s: Signal={last_clear_signal} but {last_clear_signal} "
                                f"side has no asks — SKIP BET (correct side dried up)"
                            )

        time.sleep(0.1)

    # ── Step 6: Settle Trade and Update Balances ─────────────────────────────
    net_move = last_price - ptb
    actual_dir = "UP ▲" if net_move > 0 else "DOWN ▼"

    print(f"\n  {'═'*72}")
    print(f"  ⏰ WINDOW CLOSED : {fmt_win(w_s)}")
    print(f"  📌 Price to Beat  : ${ptb:,.2f}")
    print(f"  🏁 Final Price    : ${last_price:,.2f}")
    print(f"  📊 Net move       : {net_move:>+.2f}   →  {actual_dir}")
    if decided_side:
        correct = (
            (decided_side == "UP" and net_move > 0) or
            (decided_side == "DOWN" and net_move < 0)
        )
        print(f"  🎰 Bot bet        : {decided_side} @ ${entry_price:.4f}  "
              f"→ {'CORRECT ✅' if correct else 'WRONG ❌'}")
    else:
        print("  🎰 Bot bet        : NO BET PLACED")
    print(f"  {'═'*72}")

    # Resolution Settle
    if decided_side and entry_price:
        print(f"\n  ⏳ Polling for market resolution ({slug})...")
        resolved = False
        for attempt in range(1, SETTLE_MAX_ATTEMPTS + 1):
            time.sleep(SETTLE_POLL_INTERVAL)
            up_won, prices = check_resolution(slug)
            print(f"  [settle {attempt}]  prices={[f'{p:.4f}' for p in prices]}")
            if up_won is not None:
                won = (decided_side == "UP" and up_won) or (decided_side == "DOWN" and not up_won)
                if won:
                    profit = state.stake * (1.0 / entry_price - 1.0)
                    backing_add = profit * 0.5
                    stake_add   = profit * 0.5
                    
                    print(f"\n  🏆 WIN! Net profit: +${profit:.4f}  "
                          f"(splitting 50/50: +${stake_add:.4f} to stake, +${backing_add:.4f} to backing)")
                    state.wins += 1
                    state.stake += stake_add
                    state.backing += backing_add
                else:
                    print(f"\n  ❌ LOSS! Staked amount of ${state.stake:.2f} is lost.")
                    state.losses += 1
                    # Reset stake to 1.0 from backing reserve
                    if state.backing >= 1.0:
                        state.stake = 1.0
                        state.backing -= 1.0
                        print(f"  🔄 Stake reset to $1.00 from backing reserve (Remaining reserve: ${state.backing:.2f})")
                    else:
                        state.stake = 0.0
                        print(f"  ⚠️  Reserve exhausted! Backing reserve is ${state.backing:.2f}. Cannot resume.")
                resolved = True
                break
        if not resolved:
            print("  ⚠️  Market did not resolve in time. Stake remains unchanged.")
    else:
        print("  ℹ️  No bet placed this window.")

    # Show dashboard
    state.print_dashboard()

    # If capital exhausted, exit
    if state.stake < 0.01:
        print("\n  💀 CAPITAL EXHAUSTED! Halting bot.")
        sys.exit(0)


# ── Main Entry ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Polymarket Rollover Compounding Bot")
    parser.add_argument("--start-stake",   type=float, default=1.0, help="Initial active stake size (default $1.0)")
    parser.add_argument("--start-backing", type=float, default=9.0, help="Initial reserve backing balance (default $9.0)")
    args = parser.parse_args()

    print(f"\n{'═'*72}")
    print(f"  ROLLOVER COMPOUNDING BOT STARTING")
    print(f"  Initial Active Stake    : ${args.start_stake:.2f}")
    print(f"  Initial Backing Reserve : ${args.start_backing:.2f}")
    print(f"  Total Starting capital  : ${args.start_stake + args.start_backing:.2f}")
    print(f"{'═'*72}\n")

    state = BotState(args.start_stake, args.start_backing)

    print("  Connecting to live WS feed...")
    ws = WSFeed()
    ws.start()

    # Confirm connection
    for _ in range(40):
        if ws.latest():
            break
        time.sleep(0.5)
    tick = ws.latest()
    if not tick:
        print("  ❌ Could not connect to WS — exiting.")
        sys.exit(1)
    price, _ = tick
    print(f"  ✅ Connected — BTC/USD: ${price:,.2f}")
    state.print_dashboard()

    cycle_num = 0
    while True:
        cycle_num += 1
        try:
            run_cycle(ws, state, cycle_num)
        except KeyboardInterrupt:
            print("\n  Stopped by user. Final summary:")
            state.print_dashboard()
            break
        except Exception as e:
            print(f"\n  ⚠️  Cycle error: {e} — retrying in 10s...")
            time.sleep(10)


if __name__ == "__main__":
    main()
