#!/usr/bin/env python3
"""
peak_hours_run.py — Triple Streak Hybrid Bot Optimized for High-Volatility Volatility (Peak Hours)

================================================================================
HOW THIS BOT OPERATES:
================================================================================
- Splits your wallet balance into 3 equal parts (minus a 5c fee buffer for each).
- Runs 3 concurrent compounding streaks in parallel:
  * Streak 1 (Trend-Catcher): Checks early from T-80s to T-15s. Requires a massive 
    $40.00+ move (Mega-Move) to buy early trends when liquidity is high.
  * Streak 2 (Close-Only): Checks late from T-12s to T-5s. Requires a $15.00+ move
    (Safer Close Buffer) to protect against last-second volatility spikes.
  * Streak 3 (Close-Only): Checks late from T-12s to T-5s. Requires a $15.00+ move
    (Safer Close Buffer) to protect against last-second volatility spikes.
- Safe Decimal Guard: The bot ignores decimal-only changes; it will not buy if the
  whole dollar amount of BTC has not changed from the Price to Beat.
- Each streak has a 4-Win Cap (Take Profit) to bank profits and reset.
- On win completion or loss, resets to 1/3 of the current wallet balance.

================================================================================
HOW TO RUN THIS BOT ON ANOTHER COMPUTER OR WITH A NEW WALLET:
================================================================================
Step 1: Install Python (version 3.10 or higher) on the computer.
Step 2: Copy the folder containing this bot onto the computer.
Step 3: Open your Terminal / Command Prompt, navigate to the folder, and run:
        pip install -r requirements.txt
Step 4: Run the bot:
        python peak_hours_run.py
Step 5: The bot will detect that it is a new setup and will ask you for:
        - Your Private Key (starts with 0x)
        It will automatically resolve your Polymarket proxy address and derive your API credentials.
Step 6: Press Enter to accept the balance, and the bot will handle the rest!
================================================================================
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

# ── Onboarding / Setup Assistant ────────────────────────────────────────────────
def setup_dotenv_if_missing():
    env_path = ".env"
    if not os.path.exists(env_path):
        print("\n" + "═"*72)
        print("  Polymarket Bot Onboarding Assistant")
        print("═"*72)
        print("  No '.env' configuration file detected. Let's set it up now.\n")
        
        trading_choice = input("  👉 Enable Live Trading? (yes/no) [Default yes]: ").strip().lower()
        live_trading = "True" if trading_choice in ("", "yes", "y", "true") else "False"

        if live_trading == "False":
            with open(env_path, "w") as f:
                f.write("POLYMARKET_LIVE_TRADING=False\n")
                f.write("POLYMARKET_ADDRESS=0x0000000000000000000000000000000000000000\n")
                f.write("POLYMARKET_PRIVATE_KEY=0x0000000000000000000000000000000000000000000000000000000000000000\n")
                f.write("POLYMARKET_API_KEY=\n")
                f.write("POLYMARKET_API_SECRET=\n")
                f.write("POLYMARKET_API_PASSPHRASE=\n")
            print("\n  ✅ '.env' file successfully created for Paper Trading!")
            print("═"*72 + "\n")
            return

        private_key = input("  👉 Enter your MetaMask 32-byte Private Key (starting with 0x): ").strip()
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key
            
        if len(private_key) != 66:
            print("  ❌ Error: Private key must be exactly 64 characters (or 66 with 0x). Exiting.")
            sys.exit(1)

        try:
            from eth_account import Account
            eoa_address = Account.from_key(private_key).address
            print(f"  Signer EOA Address derived: {eoa_address}")
        except Exception as e:
            print(f"  ❌ Invalid private key format: {e}. Exiting.")
            sys.exit(1)

        # Resolve Proxy Wallet Address
        print("  Resolving your Polymarket Proxy Wallet (funder)...")
        proxy_wallet = None
        try:
            url = f"https://polymarket.com/api/profile/userData?address={eoa_address}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                proxy_wallet = resp.json().get("proxyWallet")
        except Exception as e:
            print(f"  ⚠️ Warning: Could not fetch proxy wallet: {e}")

        sig_type = 0
        funder_address = eoa_address
        if proxy_wallet and proxy_wallet.lower() != eoa_address.lower():
            print(f"  👉 Found Proxy Wallet: {proxy_wallet} (holds your USDC)")
            funder_address = proxy_wallet
            sig_type = 3  # POLY_1271
        else:
            print("  👉 No active proxy wallet found. Using EOA directly.")

        # Derive API Key, Secret, Passphrase
        print("  Deriving API credentials from Polymarket L1 signature...")
        try:
            from py_clob_client_v2 import ClobClient
            client = ClobClient(
                host="https://clob.polymarket.com",
                chain_id=137,
                key=private_key,
                signature_type=sig_type,
                funder=funder_address
            )
            creds = client.create_or_derive_api_key()
            print("  ✅ Derived API Key successfully!")
        except Exception as e:
            print(f"  ❌ Error deriving API credentials: {e}. Exiting.")
            sys.exit(1)

        # Save to .env
        with open(env_path, "w") as f:
            f.write(f"POLYMARKET_LIVE_TRADING=True\n")
            f.write(f"POLYMARKET_ADDRESS={funder_address}\n")
            f.write(f"POLYMARKET_PRIVATE_KEY={private_key}\n")
            f.write(f"POLYMARKET_API_KEY={creds.api_key}\n")
            f.write(f"POLYMARKET_API_SECRET={creds.api_secret}\n")
            f.write(f"POLYMARKET_API_PASSPHRASE={creds.api_passphrase}\n")
            
        print("\n  ✅ '.env' file successfully created and saved!")
        print("  Ready to launch the bot...")
        print("═"*72 + "\n")

# Run onboarding before anything else
setup_dotenv_if_missing()

from dotenv import load_dotenv
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

# Windows
BET_WINDOW_START    = 80    # earliest check for Streak 1 (T-80s)
BET_WINDOW_END      = 5     # latest check for all (T-5s)

# Strategy Rules:
CONFIDENCE_THRESHOLD = 0.65  # dominant side must be priced at $0.65+

# Order-book probe marks (seconds before close)
PROBE_MARKS = [80, 70, 60, 50, 40, 35, 30, 25, 20, 18, 15, 12, 10, 8, 5, 3, 2, 1, 0]

SETTLE_POLL_INTERVAL = 5     # seconds between resolution checks
SETTLE_MAX_ATTEMPTS  = 60    # give up after 5 minutes


# ── Global State ────────────────────────────────────────────────────────────────
# 3 Streaks
streak_1_stake = 1.00
streak_1_wins = 0

streak_2_stake = 1.00
streak_2_wins = 0

streak_3_stake = 1.00
streak_3_wins = 0


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
            return (self._price, self._ts_ms) if (self._price is not None and self._ts_ms is not None) else None

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
                    self._ts_ms = None
                    self._price = None
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
        raw_bal = float(resp.get("balance", 0))
        return raw_bal / 1_000_000.0
    except Exception as e:
        print(f"  ⚠️ Error fetching balance: {e}")
        return None


# ── Probe + bet phase ─────────────────────────────────────────────────────────────
def run_probe_phase(ws: WSFeed, ptb: float, w_end: int, market: dict, clob_client=None):
    global streak_1_stake, streak_2_stake, streak_3_stake
    
    last_tick_ts       = None
    last_price         = ptb
    tick_count         = 0
    probes_done        = set()
    results            = []
    
    s1_decided_side    = None
    s1_entry_price     = None
    
    s2_decided_side    = None
    s2_entry_price     = None

    s3_decided_side    = None
    s3_entry_price     = None

    # Signal state
    last_clear_signal      = None
    last_clear_up_ask      = None
    last_clear_down_ask    = None
    last_clear_mark        = None

    print(f"\n  Streaming last {WAKE_UP_BEFORE}s — S1 Trend (T-80s to T-15s), S2 & S3 Close (T-12s to T-5s)")
    print(f"    - Streak 1 Stake   : ${streak_1_stake:.2f} pUSD")
    print(f"    - Streak 2 Stake   : ${streak_2_stake:.2f} pUSD")
    print(f"    - Streak 3 Stake   : ${streak_3_stake:.2f} pUSD")
    print(f"  {'─'*72}")

    while True:
        now       = time.time()
        remaining = w_end - now

        if remaining <= -3:
            break

        # Ticks
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

        # Probes
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
                current_move = last_price - ptb
                current_dir = "UP" if current_move > 0 else "DOWN"
                
                if up_ask is not None and down_ask is not None:
                    dominant = max(up_ask, down_ask)
                    new_signal = "UP" if up_ask > down_ask else "DOWN"
                    if dominant >= CONFIDENCE_THRESHOLD:
                        if new_signal != current_dir:
                            last_clear_signal = None
                            signal_tag = f"  ⚠️  conflict (signal={new_signal} vs price={current_dir}) - CLEARING"
                        else:
                            last_clear_signal = new_signal
                            last_clear_up_ask = up_ask
                            last_clear_down_ask = down_ask
                            last_clear_mark = mark
                            signal_tag = f"  📶 signal={new_signal}"
                    else:
                        signal_tag = f"  ⚠️  low confidence ({dominant:.2f} < {CONFIDENCE_THRESHOLD:.2f})"
                        last_clear_signal = None
                else:
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

                in_bet_window = (BET_WINDOW_END <= mark <= BET_WINDOW_START)
                if in_bet_window and last_clear_signal is not None:
                    # Skip bet if the whole number has not changed from PTB (decimal-only movement)
                    if int(last_price) == int(ptb):
                        continue
                        
                    # ── STREAK 1: Trend Catcher (Early-Entry: T-80s to T-15s) ──
                    if s1_decided_side is None and mark >= 15:
                        required_move = 40.0
                        abs_move = abs(last_price - ptb)
                        if abs_move >= required_move and last_clear_signal == current_dir:
                            sig_ask = up_ask if last_clear_signal == "UP" else down_ask
                            if sig_ask is not None:
                                s1_decided_side = last_clear_signal
                                s1_entry_price  = sig_ask
                                results[-1]["bet_placed"] = True
                                order_msg = "PAPER [S1]"
                                if clob_client is not None:
                                    order_msg = "LIVE [S1]"
                                    print(f"  🚀 [S1] PLACING LIVE ORDER: {s1_decided_side} outcome...")
                                    try:
                                        from py_clob_client_v2 import MarketOrderArgsV2
                                        token_id = market["up_id"] if s1_decided_side == "UP" else market["down_id"]
                                        clob_client.create_and_post_market_order(
                                            order_args=MarketOrderArgsV2(
                                                token_id=token_id, amount=streak_1_stake, side="BUY"
                                            )
                                        )
                                    except Exception as e:
                                        print(f"  ❌ [S1] Failed to place order: {e}")
                                        s1_decided_side = None

                    # ── STREAK 2 & 3: Close Guardians (Late-Entry: T-12s to T-5s) ──
                    if mark <= 12:
                        required_move = 15.0  # Safer Close Buffer for Volatility
                        abs_move = abs(last_price - ptb)
                        if abs_move >= required_move and last_clear_signal == current_dir:
                            sig_ask = up_ask if last_clear_signal == "UP" else down_ask
                            if sig_ask is not None:
                                # Streak 2
                                if s2_decided_side is None:
                                    s2_decided_side = last_clear_signal
                                    s2_entry_price  = sig_ask
                                    results[-1]["bet_placed"] = True
                                    order_msg = "PAPER [S2]"
                                    if clob_client is not None:
                                        order_msg = "LIVE [S2]"
                                        print(f"  🚀 [S2] PLACING LIVE ORDER: {s2_decided_side} outcome...")
                                        try:
                                            from py_clob_client_v2 import MarketOrderArgsV2
                                            token_id = market["up_id"] if s2_decided_side == "UP" else market["down_id"]
                                            clob_client.create_and_post_market_order(
                                                order_args=MarketOrderArgsV2(
                                                    token_id=token_id, amount=streak_2_stake, side="BUY"
                                                )
                                            )
                                        except Exception as e:
                                            print(f"  ❌ [S2] Failed to place order: {e}")
                                            s2_decided_side = None

                                # Streak 3
                                if s3_decided_side is None:
                                    s3_decided_side = last_clear_signal
                                    s3_entry_price  = sig_ask
                                    results[-1]["bet_placed"] = True
                                    order_msg = "PAPER [S3]"
                                    if clob_client is not None:
                                        order_msg = "LIVE [S3]"
                                        print(f"  🚀 [S3] PLACING LIVE ORDER: {s3_decided_side} outcome...")
                                        try:
                                            from py_clob_client_v2 import MarketOrderArgsV2
                                            token_id = market["up_id"] if s3_decided_side == "UP" else market["down_id"]
                                            clob_client.create_and_post_market_order(
                                                order_args=MarketOrderArgsV2(
                                                    token_id=token_id, amount=streak_3_stake, side="BUY"
                                                )
                                            )
                                        except Exception as e:
                                            print(f"  ❌ [S3] Failed to place order: {e}")
                                            s3_decided_side = None

        time.sleep(0.1)

    return results, s1_decided_side, s1_entry_price, s2_decided_side, s2_entry_price, s3_decided_side, s3_entry_price, last_price


# ── Settlement ────────────────────────────────────────────────────────────────────
def settle(slug, decided_side, entry_price, stake_usd, name="S1"):
    print(f"\n  ⏳ [{name}] Polling for market resolution ({slug})...")
    for attempt in range(1, SETTLE_MAX_ATTEMPTS + 1):
        time.sleep(SETTLE_POLL_INTERVAL)
        up_won, prices = check_resolution(slug)
        print(f"  [{name}-settle {attempt}]  prices={[f'{p:.4f}' for p in prices]}")
        if up_won is not None:
            actual = "UP ▲" if up_won else "DOWN ▼"
            won = (decided_side == "UP" and up_won) or (decided_side == "DOWN" and not up_won)
            pnl = stake_usd * (1 / entry_price - 1) if won else -stake_usd
            print(f"\n  ════════════════════════════════════════════════")
            print(f"  🏆 RESULT [{name}] : {'WIN  ✅' if won else 'LOSS ❌'}")
            print(f"  📌 We bet     : {decided_side}")
            print(f"  🎯 Outcome    : {actual}")
            print(f"  💰 P&L        : ${pnl:>+.4f}  (stake ${stake_usd:.2f})")
            print(f"  ════════════════════════════════════════════════\n")
            return won
    print(f"  ⚠️  [{name}] Market did not resolve within the wait period.")
    return None


# ── Summary table ─────────────────────────────────────────────────────────────────
def print_summary(results, w_start, w_end, ptb, last_price, s1_side, s1_price, s2_side, s2_price, s3_side, s3_price):
    net = last_price - ptb
    direction = "UP ▲" if net > 0 else "DOWN ▼"

    print(f"\n  {'═'*72}")
    print(f"  ⏰ WINDOW CLOSED : {fmt_win(w_start)}")
    print(f"  📌 Price to Beat  : ${ptb:,.2f}")
    print(f"  🏁 Final Price    : ${last_price:,.2f}  (next window's PTB)")
    print(f"  📊 Net move       : {net:>+.2f}   →  {direction}")
    if s1_side:
        print(f"  🎯 Bet [Streak 1] : {s1_side} @ ${s1_price:.4f} (Early Trend)")
    if s2_side:
        print(f"  🎯 Bet [Streak 2] : {s2_side} @ ${s2_price:.4f} (Late Close)")
    if s3_side:
        print(f"  🎯 Bet [Streak 3] : {s3_side} @ ${s3_price:.4f} (Late Close)")
    print(f"  {'─'*72}")
    print(f"  {'T-MARK':>8}  {'TIME':>8}  {'UP ASK':>8}  {'DOWN ASK':>9}  STATUS")
    print(f"  {'─'*72}")

    for r in results:
        up_str   = f"${r['up_ask']:.4f}"   if r["up_ask"]   else "  NONE  "
        down_str = f"${r['down_ask']:.4f}" if r["down_ask"] else "   NONE  "
        status   = "✅ OPEN" if r["has_liquidity"] else "❌ CLOSED"
        bet_tag  = "  ← BET" if r.get("bet_placed") else ""
        print(f"  T-{r['mark']:>4}s  {fmt(r['ts']):>8}  {up_str:>8}  {down_str:>9}  {status}{bet_tag}")

    print(f"  {'═'*72}\n")


# ── Entry point ───────────────────────────────────────────────────────────────────
def main():
    global streak_1_stake, streak_1_wins, streak_2_stake, streak_2_wins, streak_3_stake, streak_3_wins
    
    mode_str = "LIVE BET" if POLYMARKET_LIVE_TRADING else "PAPER BET"
    print(f"\n{'═'*72}")
    print(f"  PEAK HOURS COMPOUNDING BOT  +  {mode_str}")
    print(f"{'═'*72}\n")

    clob_client = None
    if POLYMARKET_LIVE_TRADING:
        print("  ⚠️  LIVE TRADING ENABLED! Initializing Polymarket CLOB Client...")
        if not all([POLYMARKET_ADDRESS, POLYMARKET_API_KEY, POLYMARKET_API_SECRET, POLYMARKET_API_PASSPHRASE, POLYMARKET_PRIVATE_KEY]):
            print("  ❌ Missing live credentials in .env file! Exiting.")
            sys.exit(1)
            
        try:
            from py_clob_client_v2 import ClobClient, ApiCreds
            from eth_account import Account
            
            eoa_address = Account.from_key(POLYMARKET_PRIVATE_KEY).address
            sig_type = 0
            funder_addr = None
            if POLYMARKET_ADDRESS and POLYMARKET_ADDRESS.lower() != eoa_address.lower():
                sig_type = 3
                funder_addr = POLYMARKET_ADDRESS
                print(f"  👉 Proxy Wallet: funder={funder_addr} signature_type=3 (POLY_1271).")

            creds = ApiCreds(
                api_key=POLYMARKET_API_KEY,
                api_secret=POLYMARKET_API_SECRET,
                api_passphrase=POLYMARKET_API_PASSPHRASE
            )
            clob_client = ClobClient(
                host=CLOB_HOST, chain_id=137, key=POLYMARKET_PRIVATE_KEY, creds=creds, signature_type=sig_type, funder=funder_addr
            )
            print("  ✅ CLOB Client initialized successfully.\n")
        except Exception as e:
            print(f"  ❌ Error initializing CLOB client: {e}. Exiting.")
            sys.exit(1)

    print("  Connecting to Polymarket WS feed...")
    ws = WSFeed()
    ws.start()

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

    # ── Initial Balance check & Split ──────────────────────────────────────────────
    if POLYMARKET_LIVE_TRADING and clob_client is not None:
        print("  🔄 Querying live wallet balance...")
        bal = get_live_balance(clob_client)
        if bal is not None:
            print(f"  💰 Live Balance: ${bal:.2f} pUSD")
            suggested_split = max(1.00, round((bal - 0.15) / 3.0, 2))
        else:
            suggested_split = 1.00
            
        try:
            user_in = input(f"  👉 Enter starting stake for each streak [Default ${suggested_split:.2f}]: ").strip()
            starting_stake = float(user_in) if user_in else suggested_split
        except ValueError:
            starting_stake = suggested_split

        streak_1_stake = starting_stake
        streak_2_stake = starting_stake
        streak_3_stake = starting_stake
    else:
        starting_stake = 1.00
        streak_1_stake = 1.00
        streak_2_stake = 1.00
        streak_3_stake = 1.00

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
            print(f"  [S1] Streak 1  : {streak_1_wins}/{STREAK_WIN_CAP} Wins  |  Stake: ${streak_1_stake:.2f} pUSD (Trend)")
            print(f"  [S2] Streak 2  : {streak_2_wins}/{STREAK_WIN_CAP} Wins  |  Stake: ${streak_2_stake:.2f} pUSD (Close)")
            print(f"  [S3] Streak 3  : {streak_3_wins}/{STREAK_WIN_CAP} Wins  |  Stake: ${streak_3_stake:.2f} pUSD (Close)")
            print(f"  Bet window     : T-{BET_WINDOW_START}s → T-{BET_WINDOW_END}s")
            print(f"{'═'*72}\n")

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

            wake_at   = w_e - WAKE_UP_BEFORE
            wait_secs = wake_at - time.time()
            if wait_secs > 0:
                print(f"  ⏳ Sleeping {int(wait_secs)}s — will wake up at T-{WAKE_UP_BEFORE}s ({fmt(wake_at)})...\n")
                time.sleep(wait_secs)

            # ── Run the probe + bet phase ─────────────────────────────────────────────
            results, s1_side, s1_price, s2_side, s2_price, s3_side, s3_price, last_price = run_probe_phase(
                ws, ptb, w_e, market, clob_client=clob_client
            )

            # ── Window close summary ──────────────────────────────────────────────────
            print_summary(results, w_s, w_e, ptb, last_price, s1_side, s1_price, s2_side, s2_price, s3_side, s3_price)

            # ── Settlement calculations ────────────────────────────────────────
            actual_direction = "UP" if (last_price > ptb) else "DOWN"

            # Settle S1
            s1_old = streak_1_stake
            if s1_side and s1_price:
                s1_won = (s1_side == actual_direction)
                if s1_won:
                    streak_1_wins += 1
                    streak_1_stake = round(s1_old / s1_price, 2)
                    print(f"  💰 [S1 WIN] Win {streak_1_wins}/{STREAK_WIN_CAP}! Payout rolled over: ${streak_1_stake:.2f} pUSD")
                    if streak_1_wins >= STREAK_WIN_CAP:
                        print(f"  🏆 [S1 COMPLETED] Resetting streak 1...")
                        bal = get_live_balance(clob_client) if clob_client else None
                        streak_1_stake = max(1.00, round((bal - 0.15) / 3.0, 2)) if bal else 1.00
                        streak_1_wins = 0
                else:
                    print(f"  ❌ [S1 LOSS] Resetting streak 1.")
                    bal = get_live_balance(clob_client) if clob_client else None
                    streak_1_stake = max(1.00, round((bal - 0.15) / 3.0, 2)) if bal else 1.00
                    streak_1_wins = 0
                
                threading.Thread(target=settle, args=(slug, s1_side, s1_price, s1_old, "S1"), daemon=True).start()

            # Settle S2
            s2_old = streak_2_stake
            if s2_side and s2_price:
                s2_won = (s2_side == actual_direction)
                if s2_won:
                    streak_2_wins += 1
                    streak_2_stake = round(s2_old / s2_price, 2)
                    print(f"  💰 [S2 WIN] Win {streak_2_wins}/{STREAK_WIN_CAP}! Payout rolled over: ${streak_2_stake:.2f} pUSD")
                    if streak_2_wins >= STREAK_WIN_CAP:
                        print(f"  🏆 [S2 COMPLETED] Resetting streak 2...")
                        bal = get_live_balance(clob_client) if clob_client else None
                        streak_2_stake = max(1.00, round((bal - 0.15) / 3.0, 2)) if bal else 1.00
                        streak_2_wins = 0
                else:
                    print(f"  ❌ [S2 LOSS] Resetting streak 2.")
                    bal = get_live_balance(clob_client) if clob_client else None
                    streak_2_stake = max(1.00, round((bal - 0.15) / 3.0, 2)) if bal else 1.00
                    streak_2_wins = 0
                
                threading.Thread(target=settle, args=(slug, s2_side, s2_price, s2_old, "S2"), daemon=True).start()

            # Settle S3
            s3_old = streak_3_stake
            if s3_side and s3_price:
                s3_won = (s3_side == actual_direction)
                if s3_won:
                    streak_3_wins += 1
                    streak_3_stake = round(s3_old / s3_price, 2)
                    print(f"  💰 [S3 WIN] Win {streak_3_wins}/{STREAK_WIN_CAP}! Payout rolled over: ${streak_3_stake:.2f} pUSD")
                    if streak_3_wins >= STREAK_WIN_CAP:
                        print(f"  🏆 [S3 COMPLETED] Resetting streak 3...")
                        bal = get_live_balance(clob_client) if clob_client else None
                        streak_3_stake = max(1.00, round((bal - 0.15) / 3.0, 2)) if bal else 1.00
                        streak_3_wins = 0
                else:
                    print(f"  ❌ [S3 LOSS] Resetting streak 3.")
                    bal = get_live_balance(clob_client) if clob_client else None
                    streak_3_stake = max(1.00, round((bal - 0.15) / 3.0, 2)) if bal else 1.00
                    streak_3_wins = 0
                
                threading.Thread(target=settle, args=(slug, s3_side, s3_price, s3_old, "S3"), daemon=True).start()

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
