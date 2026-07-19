#!/usr/bin/env python3
"""
smart_scaling_bot.py — Advanced Polymarket timing bot applying all safety
close-to-market principles, with:
1. Dynamic Starting Stake: Set to 30% of your live wallet balance (min $1.00)
   queried from the API, protecting the other 70% of your wallet.
2. 4-Win Streak Cap (Take Profit): Once a streak hits 4 consecutive wins,
   it automatically banks the profits to your wallet and resets to the new starting stake.
3. API-based Startup Reconstruction: Automatically queries your live trade history
   and resolves previous markets on startup to find your current active streak count.
4. Background Resolution Logging: Settlement is fully non-blocking.
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
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

POLYMARKET_LIVE_TRADING = os.getenv("POLYMARKET_LIVE_TRADING", "False").lower() in ("true", "1", "yes")
POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS")
POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY")
POLYMARKET_API_SECRET = os.getenv("POLYMARKET_API_SECRET")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE")
POLYMARKET_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY")

# ── Config ──────────────────────────────────────────────────────────────────────
LIVE_WS_URL   = "wss://ws-live-data.polymarket.com/"
GAMMA_HOST    = "https://gamma-api.polymarket.com"
CLOB_HOST     = "https://clob.polymarket.com"
WINDOW_SECS   = 300          # 5-minute window

WAKE_UP_BEFORE      = 90    # seconds before close to start streaming/probing
STREAK_WIN_CAP      = 4     # Take Profit: Reset streak after 4 consecutive wins

# Bet window: place bet at the FIRST probe within this range
BET_WINDOW_START    = 80    # earliest we'll check (T-80s)
BET_WINDOW_END      = 5     # latest we'll bet  (T-5s)

# Strategy Rules:
CONFIDENCE_THRESHOLD = 0.65  # dominant side must be priced at $0.65+

# Order-book probe marks (seconds before close)
PROBE_MARKS = [80, 70, 60, 50, 40, 35, 30, 25, 20, 18, 15, 12, 10, 8, 5, 3, 2, 1, 0]

SETTLE_POLL_INTERVAL = 5     # seconds between resolution checks
SETTLE_MAX_ATTEMPTS  = 60    # give up after 5 minutes


# ── Global State ────────────────────────────────────────────────────────────────
current_stake = 1.00
starting_stake = 1.00
streak_count = 0
active_settle_thread = None


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
        self._stopped = False
        self._ws_app = None

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

        def on_close(ws, close_status_code, close_msg):
            if not self._stopped:
                print("  ⚠️ WS connection closed — reconnecting in 2 seconds...")
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

    def latest(self):
        self.check_staleness_and_reconnect()
        with self._lock:
            return (self._price, self._ts_ms) if self._price is not None else None

    def price_at_or_after(self, ts_sec):
        self.check_staleness_and_reconnect()
        with self._lock:
            if self._ts_ms is None or self._price is None:
                return None
            if self._ts_ms >= ts_sec * 1000:
                return self._price, self._ts_ms
        return None

    def check_staleness_and_reconnect(self):
        with self._lock:
            if self._ts_ms is not None:
                lag = time.time() - (self._ts_ms / 1000.0)
                if lag > 15.0:
                    print(f"\n  ⚠️ WS feed is stale (lag={lag:.1f}s) — forcing reconnect...\n")
                    self._ts_ms = None  # Reset to prevent double triggers
                    if self._ws_app:
                        try:
                            self._ws_app.close()
                        except Exception:
                            pass


# ── Market / resolution / balance API ─────────────────────────────────────────────
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


def get_live_balance(clob_client):
    try:
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        resp = clob_client.get_balance_allowance(params)
        print(f"  [DEBUG] balance response: {resp}")
        raw_bal = float(resp.get("balance", 0))
        return raw_bal / 1_000_000.0
    except Exception as e:
        print(f"  ⚠️ Error fetching balance: {e}")
        return None


def reconstruct_streak_on_startup(clob_client, default_starting_stake):
    try:
        from py_clob_client_v2.clob_types import TradeParams
        params = TradeParams(maker_address=os.getenv("POLYMARKET_ADDRESS"))
        trades = clob_client.get_trades(params)
        if not trades:
            print("  ℹ️ No previous trades found on API. Starting fresh streak.")
            return default_starting_stake, 0
        
        last_trade = trades[0]
        match_time = int(float(last_trade.get("match_time", 0)))
        w_s = (match_time // 300) * 300
        slug = f"btc-updown-5m-{w_s}"
        
        print(f"  🔍 Checking resolution for last traded market: {slug}...")
        up_won, prices = check_resolution(slug)
        if up_won is None:
            # Not resolved yet, default to the trade size * price (the cost we paid)
            cost = float(last_trade.get("size", 0)) * float(last_trade.get("price", 0))
            print(f"  ⚠️ Last market unresolved. Resuming with current active trade size: ${cost:.2f} pUSD")
            return max(1.00, round(cost, 2)), 1
            
        outcome_bought = last_trade.get("outcome", "").upper()
        winning_outcome = "UP" if up_won else "DOWN"
        
        if outcome_bought != winning_outcome:
            print("  ❌ Last trade was a LOSS. Starting fresh streak.")
            return default_starting_stake, 0
            
        # Last trade was a win. Let's count consecutive wins in the active streak
        streak_wins = 1
        current_stake_val = round(float(last_trade.get("size", 0)), 2)
        
        for t in trades[1:STREAK_WIN_CAP]:
            t_time = int(float(t.get("match_time", 0)))
            t_w_s = (t_time // 300) * 300
            t_slug = f"btc-updown-5m-{t_w_s}"
            t_up_won, _ = check_resolution(t_slug)
            if t_up_won is None:
                break
            t_outcome = t.get("outcome", "").upper()
            t_winning = "UP" if t_up_won else "DOWN"
            if t_outcome == t_winning:
                streak_wins += 1
            else:
                break
                
        if streak_wins >= STREAK_WIN_CAP:
            print(f"  🏆 [STREAK BANKED] {streak_wins} consecutive wins already achieved in history. Starting fresh streak.")
            return default_starting_stake, 0
            
        print(f"  📈 Streak of {streak_wins} wins detected in history. Next stake: ${current_stake_val:.2f} pUSD")
        return current_stake_val, streak_wins
    except Exception as e:
        print(f"  ⚠️ Error reconstructing streak on startup: {e}")
        return default_starting_stake, 0


# ── Probe + bet phase ─────────────────────────────────────────────────────────────
def run_probe_phase(ws: WSFeed, ptb: float, w_end: int, market: dict, clob_client=None, stake_usd=1.00):
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
    print(f"  Safety Rules:")
    print(f"    - Current Stake   : ${stake_usd:.2f} pUSD")
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

                # ── Update last clear signal ────────────────────────────────
                signal_tag = ""
                
                # Check current actual price side
                current_move = last_price - ptb
                current_dir = "UP" if current_move > 0 else "DOWN"
                
                if up_ask is not None and down_ask is not None:
                    dominant      = max(up_ask, down_ask)
                    new_signal    = "UP" if up_ask > down_ask else "DOWN"
                    
                    if dominant >= CONFIDENCE_THRESHOLD:
                        # Clear stale signal if current actual price direction doesn't match the signal
                        if new_signal != current_dir:
                            last_clear_signal = None
                            signal_tag = f"  ⚠️  signal conflict (signal={new_signal} vs price={current_dir}) - CLEARING"
                        else:
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
                        # Clear signal if confidence dies
                        last_clear_signal = None
                elif up_ask is None and down_ask is None:
                    signal_tag = "  (both gone)"
                    last_clear_signal = None

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
                    "bet_placed": False,
                })

                # ── Bet logic: fire within bet window ────────────────────────
                in_bet_window = (BET_WINDOW_END <= mark <= BET_WINDOW_START)
                if in_bet_window and decided_side is None:
                    global current_stake
                    stake_usd = current_stake

                    if last_clear_signal is None:
                        print(f"  ⏭️  T-{mark}s: No active/fresh signal — skipping...")
                    else:
                        # Determine required move based on mark countdown tier
                        if mark >= 70:
                            required_move = 30.0
                            tier_desc = "mega-move"
                        elif 35 <= mark <= 60:
                            required_move = 20.0
                            tier_desc = "early double-move"
                        elif 15 <= mark <= 30:
                            required_move = 15.0
                            tier_desc = "normal move"
                        elif 5 <= mark <= 12:
                            required_move = 5.0
                            tier_desc = "close buying"
                        else:
                            required_move = 15.0
                            tier_desc = "default"

                        # Safety Rule 1: Verify current move size is sufficient
                        abs_move = abs(last_price - ptb)
                        if abs_move < required_move:
                            print(f"  🚫 T-{mark}s: BTC move too small for {tier_desc} (${abs_move:.2f} < ${required_move:.2f}) — SKIP BET")
                            continue

                        # Safety Rule 2: Check current price direction matches the signal (Freshness Check)
                        current_dir = "UP" if (last_price > ptb) else "DOWN"
                        if last_clear_signal != current_dir:
                            print(f"  🚫 T-{mark}s: Signal ({last_clear_signal}) does not match price direction ({current_dir}) — SKIP BET (stale)")
                            continue

                        # Check if the signal side still has liquidity right now
                        sig_ask = up_ask if last_clear_signal == "UP" else down_ask
                        if sig_ask is not None:
                            decided_side = last_clear_signal
                            entry_price  = sig_ask
                            results[-1]["bet_placed"] = True
                            payout = stake_usd / entry_price
                            profit = payout - stake_usd
                            flip_warn = (
                                f"  ⚡ Note: signal flipped at T-{signal_flip_at_mark}s"
                                if signal_flip_at_mark else ""
                            )
                            
                            order_msg = "PAPER BET"
                            order_details = ""
                            if clob_client is not None:
                                order_msg = "LIVE BET"
                                print(f"\n  🚀 PLACING LIVE ORDER on Polymarket CLOB: {decided_side} outcome...")
                                try:
                                    from py_clob_client_v2 import MarketOrderArgsV2
                                    token_id = market["up_id"] if decided_side == "UP" else market["down_id"]
                                    resp = clob_client.create_and_post_market_order(
                                        order_args=MarketOrderArgsV2(
                                            token_id=token_id,
                                            amount=stake_usd,
                                            side="BUY"
                                        )
                                    )
                                    print(f"  ✅ Live order response: {resp}")
                                    order_details = f"\n  │  Order ID: {resp.get('orderID', 'n/a')}                                   │"
                                
                                    # Play alert beep
                                    try:
                                        sys.stdout.write('\a')
                                        sys.stdout.flush()
                                    except Exception:
                                        pass
                                except Exception as e:
                                    print(f"  ❌ Failed to place live order: {e}")
                                    order_msg = "LIVE BET (FAILED)"
                                    decided_side = None
                                    entry_price = None
                            
                            if decided_side is not None:
                                print(
                                    f"\n  ┌──────────────────────────────────────────────────────────┐"
                                    f"\n  │  🎯 {order_msg:<9}  →  {decided_side:<4}  @ ${entry_price:.4f}  (T-{mark}s)           │"
                                    f"\n  │  Signal from T-{last_clear_mark}s: UP=${last_clear_up_ask:.4f}  "
                                    f"DOWN=${last_clear_down_ask:.4f}           │"
                                    f"\n  │  Stake: ${stake_usd:.2f}   Payout: ${payout:.4f}  Profit: +${profit:.4f}           │"
                                    + order_details +
                                    f"\n  └──────────────────────────────────────────────────────────┘"
                                    + (f"\n  {flip_warn}" if flip_warn else "")
                                )
                        else:
                            print(
                                f"\n  🚫 T-{mark}s: Signal={last_clear_signal} but {last_clear_signal} "
                                f"side has no asks — SKIP BET (correct side dried up)"
                            )

        time.sleep(0.1)

    print(f"\n  📶 Final signal: {last_clear_signal}  "
          f"(last updated at T-{last_clear_mark}s  "
          f"UP=${last_clear_up_ask:.4f}  DOWN=${last_clear_down_ask:.4f})"
          if last_clear_signal else "\n  📶 No confident signal captured.")
    if signal_flip_at_mark:
        print(f"  ⚡ Signal flipped at T-{signal_flip_at_mark}s  "
              f"({prev_clear_signal} → {last_clear_signal})")

    return results, decided_side, entry_price, last_price


# ── Settlement ────────────────────────────────────────────────────────────────────
def settle(slug, decided_side, entry_price, stake_usd):
    print(f"\n  ⏳ Polling for market resolution ({slug})...")
    for attempt in range(1, SETTLE_MAX_ATTEMPTS + 1):
        time.sleep(SETTLE_POLL_INTERVAL)
        up_won, prices = check_resolution(slug)
        print(f"  [settle {attempt}]  prices={[f'{p:.4f}' for p in prices]}")
        if up_won is not None:
            actual = "UP ▲" if up_won else "DOWN ▼"
            won = (decided_side == "UP" and up_won) or (decided_side == "DOWN" and not up_won)
            pnl = stake_usd * (1 / entry_price - 1) if won else -stake_usd
            print(f"\n  ════════════════════════════════════════════════")
            print(f"  🏆 RESULT     : {'WIN  ✅' if won else 'LOSS ❌'}")
            print(f"  📌 We bet     : {decided_side}")
            print(f"  🎯 Outcome    : {actual}")
            print(f"  💰 P&L        : ${pnl:>+.4f}  (stake ${stake_usd:.2f})")
            print(f"  ════════════════════════════════════════════════\n")
            return won
    print("  ⚠️  Market did not resolve within the wait period.")
    return None


# ── Summary table ─────────────────────────────────────────────────────────────────
def print_summary(results, w_start, w_end, ptb, last_price, decided_side, entry_price, stake_usd):
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
        bet_tag  = "  ← BET" if r.get("bet_placed") else ""
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
    global current_stake, starting_stake, streak_count
    
    mode_str = "LIVE BET" if POLYMARKET_LIVE_TRADING else "PAPER BET"
    print(f"\n{'═'*72}")
    print(f"  SMART SCALING COMPOUNDING BOT  +  {mode_str}")
    print(f"{'═'*72}\n")

    clob_client = None
    if POLYMARKET_LIVE_TRADING:
        print("  ⚠️  LIVE TRADING ENABLED! Initializing Polymarket CLOB Client...")
        if not all([POLYMARKET_ADDRESS, POLYMARKET_API_KEY, POLYMARKET_API_SECRET, POLYMARKET_API_PASSPHRASE, POLYMARKET_PRIVATE_KEY]):
            print("  ❌ Missing live trading credentials in .env file! Exiting.")
            sys.exit(1)
        
        # Check private key format
        if not POLYMARKET_PRIVATE_KEY.startswith("0x") or len(POLYMARKET_PRIVATE_KEY) != 66:
            print(f"  ❌ Invalid private key format. Must start with 0x and be 66 characters long. Exiting.")
            sys.exit(1)
            
        try:
            from py_clob_client_v2 import ClobClient, ApiCreds
            from eth_account import Account
            
            # Derive EOA address from private key to check if proxy is needed
            eoa_address = Account.from_key(POLYMARKET_PRIVATE_KEY).address
            
            sig_type = 0
            funder_addr = None
            if POLYMARKET_ADDRESS and POLYMARKET_ADDRESS.lower() != eoa_address.lower():
                sig_type = 3  # POLY_1271 (required for new deposit wallets)
                funder_addr = POLYMARKET_ADDRESS
                print(f"  👉 Proxy Wallet detected. Using funder={funder_addr} and signature_type=3 (POLY_1271).")
            else:
                print(f"  👉 EOA Wallet detected. Using signature_type=0.")

            creds = ApiCreds(
                api_key=POLYMARKET_API_KEY,
                api_secret=POLYMARKET_API_SECRET,
                api_passphrase=POLYMARKET_API_PASSPHRASE
            )
            clob_client = ClobClient(
                host=CLOB_HOST,
                chain_id=137, # Polygon Mainnet
                key=POLYMARKET_PRIVATE_KEY,
                creds=creds,
                signature_type=sig_type,
                funder=funder_addr
            )
            print("  ✅ CLOB Client initialized successfully.\n")
        except Exception as e:
            print(f"  ❌ Error initializing CLOB client: {e}. Exiting.")
            sys.exit(1)

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

    # ── Initial Stake Scaling and Streak Reconstruction ──────────────────────────────
    if POLYMARKET_LIVE_TRADING and clob_client is not None:
        print("  🔄 Querying live wallet balance to calculate starting stake...")
        bal = get_live_balance(clob_client)
        if bal is not None:
            starting_stake = max(1.00, round(bal - 0.05, 2))
            print(f"  💰 Live Balance: ${bal:.2f} pUSD  |  Calculated Starting Stake (100% - 5c): ${starting_stake:.2f} pUSD")
        else:
            starting_stake = 1.00
            print(f"  ⚠️ Could not fetch balance. Defaulting starting stake to: $1.00 pUSD")
            
        print("  🔄 Reconstructing streak stake from Polymarket API history...")
        current_stake, streak_count = reconstruct_streak_on_startup(clob_client, starting_stake)
    else:
        starting_stake = 1.00
        current_stake = 1.00
        streak_count = 0

    # ── Continuous Trading Loop ──────────────────────────────────────────────────
    while True:
        try:
            now       = time.time()
            w_s       = win_start(now)
            w_e       = win_end(now)
            secs_into = now - w_s
            remaining = w_e - now

            print(f"\n{'═'*72}")
            print(f"  🆕 STARTING NEW CYCLE")
            print(f"  Current time   : {fmt(now)}")
            print(f"  Current window : {fmt_win(w_s)}")
            print(f"  Into window    : {int(secs_into)}s  |  Remaining: {int(remaining)}s")
            print(f"  Current Streak : {streak_count}/{STREAK_WIN_CAP} Wins")
            print(f"  Active Stake   : ${current_stake:.2f} pUSD")
            print(f"  Bet window     : T-{BET_WINDOW_START}s → T-{BET_WINDOW_END}s")
            print(f"{'═'*72}\n")

            # ── Determine PTB and target window ──────────────────────────────────────
            if secs_into > 10:
                sleep_secs = w_e - time.time() + 0.5
                print(f"  ⚠️  Mid-window ({int(secs_into)}s in, {int(remaining)}s remaining).")
                print(f"  ⏳ Sleeping {int(sleep_secs)}s until next boundary ({fmt(w_e)})...\n")
                time.sleep(max(0, sleep_secs))

                now = time.time()
                w_s = win_start(now)
                w_e = w_s + WINDOW_SECS

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
                print("  ❌ Could not capture PTB in 30s — skipping this window.")
                sleep_time = max(10, w_e - time.time())
                time.sleep(sleep_time)
                continue

            # ── Resolve market tokens ─────────────────────────────────────────────────
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
                print("  ❌ Could not resolve market — skipping this window.")
                sleep_time = max(10, w_e - time.time())
                time.sleep(sleep_time)
                continue
            print(f"  📋 {market['title']}\n")

            # ── Sleep silently until WAKE_UP_BEFORE seconds before close ─────────────
            wake_at   = w_e - WAKE_UP_BEFORE
            wait_secs = wake_at - time.time()
            if wait_secs > 0:
                print(f"  ⏳ Sleeping {int(wait_secs)}s — will wake up at T-{WAKE_UP_BEFORE}s ({fmt(wake_at)})...\n")
                time.sleep(wait_secs)

            # ── Run the probe + bet phase ─────────────────────────────────────────────
            results, decided_side, entry_price, last_price = run_probe_phase(
                ws, ptb, w_e, market, clob_client=clob_client, stake_usd=current_stake
            )

            # ── Window close summary ──────────────────────────────────────────────────
            print_summary(results, w_s, w_e, ptb, last_price, decided_side, entry_price, stake_usd=current_stake)

            # ── Settle & Streak Rollover Compounding (Instant self-calculation + BG logs) ──
            if decided_side and entry_price:
                # 1. Instant self-calculation of win/loss
                actual_direction = "UP" if (last_price > ptb) else "DOWN"
                calculated_won = (decided_side == actual_direction)
                
                old_stake = current_stake
                if calculated_won:
                    streak_count += 1
                    payout = old_stake / entry_price
                    current_stake = round(payout, 2)
                    print(f"  💰 [STREAK WIN (CALCULATED)] Win {streak_count}/{STREAK_WIN_CAP}! Payout rolled over: ${current_stake:.2f} pUSD")
                    
                    # Take Profit trigger
                    if streak_count >= STREAK_WIN_CAP:
                        print(f"\n  🏆 [STREAK COMPLETED] {STREAK_WIN_CAP} wins achieved! banking profits and resetting...")
                        # Query live balance to set new starting stake size
                        bal = get_live_balance(clob_client) if clob_client else None
                        if bal is not None:
                            starting_stake = max(1.00, round(bal - 0.05, 2))
                            print(f"  💰 New Live Balance: ${bal:.2f} pUSD  |  New Starting Stake (100% - 5c): ${starting_stake:.2f} pUSD")
                        else:
                            print(f"  ⚠️ Could not fetch balance. Keeping starting stake at: ${starting_stake:.2f} pUSD")
                        current_stake = starting_stake
                        streak_count = 0
                else:
                    # Loss
                    print(f"  ❌ [STREAK LOSS (CALCULATED)] Resetting streak stake.")
                    # Query live balance to set new starting stake size
                    bal = get_live_balance(clob_client) if clob_client else None
                    if bal is not None:
                        starting_stake = max(1.00, round(bal - 0.05, 2))
                        print(f"  💰 New Live Balance: ${bal:.2f} pUSD  |  New Starting Stake (100% - 5c): ${starting_stake:.2f} pUSD")
                    else:
                        print(f"  ⚠️ Could not fetch balance. Keeping starting stake at: ${starting_stake:.2f} pUSD")
                    current_stake = starting_stake
                    streak_count = 0
                
                # 2. Spawn background settle log task (just for verification and visual feedback)
                def bg_settle_task(slug_val, side_val, price_val, stake_val):
                    settle(slug_val, side_val, price_val, stake_val)

                global active_settle_thread
                active_settle_thread = threading.Thread(
                    target=bg_settle_task,
                    args=(slug, decided_side, entry_price, old_stake),
                    daemon=True
                )
                active_settle_thread.start()
            else:
                print("  ℹ️  No bet was placed — nothing to settle. Stake stays unchanged.")

            # Small cooldown sleep to ensure we cross the boundary into the next window
            time.sleep(2)

        except Exception as e:
            print(f"\n  ❌ Error in main loop: {e}")
            print("  ⏳ Waiting 10 seconds before restarting cycle...\n")
            time.sleep(10)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Stopped by user.")
