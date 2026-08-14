#!/usr/bin/env python3
"""
off_peak_5mins_hybrid_sprint.py — Off-Peak Guardrailed 5-Min Hybrid Compounding Bot

================================================================================
HOW THIS OFF-PEAK HYBRID BOT OPERATES:
================================================================================
Designed specifically for Off-Peak / Late-Night Hours (thin liquidity, choppy markets):

1. Shrink Bet Window (BET_WINDOW_START = 25s):
   - Streak 1 checks only from T-25s to T-5s (cuts out 55 seconds of off-peak price drift).

2. Max Entry Price Cap (MAX_EARLY_PRICE = 0.75):
   - Never buys contracts priced above $0.75. Guarantees at least a 33%+ profit payout 
     on every winning trade and avoids terrible risk/reward setups.

3. Increased Price Distance Guard ($25.00+ Move):
   - Requires BTC to be at least $25.00 away from PTB before entering, avoiding 
     trades when BTC is hovering near the PTB line.

4. Phase 1 Sprint (Wallet < $10.00) & Phase 2 Compounding (Wallet >= $10.00):
   - Phase 1: 100% wallet stake sprint to $10.00.
   - Phase 2: 50/50 split between Streak 1 (All-Rules Guarded) and Streak 2 (Close-Only).
   - 4-Win Cap (Take Profit) per streak to bank gains and reset safely.
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
        print("  Polymarket Off-Peak Bot Onboarding Assistant")
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

WAKE_UP_BEFORE      = 55    # seconds before close to start streaming/probing
STREAK_WIN_CAP      = 4     # Take Profit: Reset streak after 4 consecutive wins

# OFF-PEAK GUARDRAILS
BET_WINDOW_START    = 40    # earliest check for Streak 1 (T-40s)
BET_WINDOW_END      = 5     # latest check for all (T-5s)
MAX_EARLY_PRICE      = 0.75  # Max price allowed ($0.75 guarantees >= 33% profit payout)
MIN_MOVE_REQUIRED   = 10.0  # BTC must be at least $10.00 away from PTB

CONFIDENCE_THRESHOLD = 0.65  # dominant side must be priced at $0.65+ (65% confidence)
PROBE_MARKS = [40, 35, 30, 25, 20, 18, 15, 12, 10, 8, 5, 3, 2, 1, 0]
AUTO_CUTOFF_HOUR_GMT = 4     # Cutoff bot immediately at 4:00 AM GMT (UTC)

SETTLE_POLL_INTERVAL = 5
SETTLE_MAX_ATTEMPTS  = 60

STATE_FILE = "sprint_state.json"

# ── Global State ────────────────────────────────────────────────────────────────
sprint_stake = 1.00
sprint_wins = 0

streak_1_stake = 1.00
streak_1_wins = 0
streak_2_stake = 1.00
streak_2_wins = 0

active_settle_thread = None

# ── State Persistence Helpers ───────────────────────────────────────────────────
def save_state():
    try:
        state = {
            "sprint_stake": sprint_stake,
            "sprint_wins": sprint_wins,
            "streak_1_stake": streak_1_stake,
            "streak_1_wins": streak_1_wins,
            "streak_2_stake": streak_2_stake,
            "streak_2_wins": streak_2_wins
        }
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        print(f"  ⚠️ Error saving state file: {e}")

def load_state():
    global sprint_stake, sprint_wins, streak_1_stake, streak_1_wins, streak_2_stake, streak_2_wins
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            sprint_stake = state.get("sprint_stake", 1.00)
            sprint_wins = state.get("sprint_wins", 0)
            streak_1_stake = state.get("streak_1_stake", 1.00)
            streak_1_wins = state.get("streak_1_wins", 0)
            streak_2_stake = state.get("streak_2_stake", 1.00)
            streak_2_wins = state.get("streak_2_wins", 0)
            print(f"  📂 Loaded state from {STATE_FILE}.")
            return True
        except Exception as e:
            print(f"  ⚠️ Error loading state file: {e}")
    return False

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
                print("  ⚠️  WS feed disconnected — reconnecting in 2s...")
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
                    print(f"  ⚠️  WS feed stale (lag={lag:.1f}s) — reconnecting...")
                    self._ts_ms = None
                    self._price = None
                    if self._ws_app:
                        try:
                            self._ws_app.close()
                        except Exception:
                            pass

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
        print(f"  ⚠️ Error fetching live balance: {e}")
        return None

# ── Probe + bet phase ─────────────────────────────────────────────────────────────
def run_probe_phase(ws: WSFeed, ptb: float, w_end: int, market: dict, clob_client=None, phase=1):
    global sprint_stake, streak_1_stake, streak_2_stake
    results = []
    tick_count = 0
    last_tick_ts = None
    last_price   = ptb
    probes_done  = set()

    s1_decided_side = None
    s1_entry_price  = None

    s2_decided_side = None
    s2_entry_price  = None

    last_clear_signal = None

    print(f"  Streaming T-{BET_WINDOW_START}s to T-0s — OFF-PEAK Guardrails Active")
    print(f"  Max Price Cap: ${MAX_EARLY_PRICE:.2f}  |  Min Distance: ${MIN_MOVE_REQUIRED:.2f}")
    print("  " + "─"*72)

    while True:
        now       = time.time()
        remaining = w_end - now

        if remaining <= -3:
            break

        ws_data = ws.latest()
        if ws_data:
            price, ts_ms = ws_data
            if ts_ms != last_tick_ts:
                last_tick_ts = ts_ms
                tick_count  += 1
                last_price   = price
                diff = price - ptb
                arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "─")
                print(
                    f"  tick #{tick_count:>3}  {fmt(now)}  $ {price:,.2f}  {arrow}  "
                    f"{diff:>+6.2f}  ptb=${ptb:,.2f}  {Math.max(0, Math.round(remaining)) if False else int(max(0, remaining)):>3}s left",
                    end=""
                )

        for mark in PROBE_MARKS:
            if mark in probes_done:
                continue
            if remaining <= mark:
                probes_done.add(mark)
                up_ask,   _ = probe_book(market["up_id"])
                down_ask, _ = probe_book(market["down_id"])

                has_liq = (up_ask is not None) and (down_ask is not None)
                results.append({
                    "mark": mark, "ts": time.time(),
                    "up_ask": up_ask, "down_ask": down_ask,
                    "has_liquidity": has_liq, "bet_placed": False,
                })

                up_str   = f"${up_ask:.4f}"   if up_ask   else "NONE"
                down_str = f"${down_ask:.4f}" if down_ask else "NONE"
                print(f"\n  ► PROBE T-{mark:>2}s  UP={up_str:<7}  DOWN={down_str:<7}  BTC=${last_price:,.2f}", end="")

                current_move = last_price - ptb
                current_dir = "UP" if current_move > 0 else "DOWN"

                if up_ask is not None and down_ask is not None:
                    dominant = max(up_ask, down_ask)
                    new_signal = "UP" if up_ask > down_ask else "DOWN"
                    if dominant >= CONFIDENCE_THRESHOLD:
                        if new_signal != current_dir:
                            last_clear_signal = None
                        else:
                            last_clear_signal = new_signal
                    else:
                        last_clear_signal = None
                else:
                    last_clear_signal = None

                in_bet_window = (BET_WINDOW_END <= mark <= BET_WINDOW_START)
                if in_bet_window:
                    if int(last_price) == int(ptb):
                        continue

                    # ── Phase 1: Sprint Mode ──
                    if phase == 1:
                        if s1_decided_side is None and last_clear_signal is not None:
                            if abs(last_price - ptb) >= MIN_MOVE_REQUIRED and last_clear_signal == current_dir:
                                sig_ask = up_ask if last_clear_signal == "UP" else down_ask
                                if sig_ask is not None:
                                    if sig_ask > MAX_EARLY_PRICE:
                                        print(f"\n  ⚠️ [OFF-PEAK SPRINT] Skipping bet: price is too expensive (${sig_ask:.4f} > ${MAX_EARLY_PRICE:.2f}).")
                                        continue

                                    s1_decided_side = last_clear_signal
                                    s1_entry_price  = sig_ask
                                    results[-1]["bet_placed"] = True

                                    order_msg = "PAPER OFF-PEAK SPRINT"
                                    if clob_client is not None:
                                        order_msg = "LIVE OFF-PEAK SPRINT"
                                        print(f"\n  🚀 [SPRINT] PLACING LIVE ORDER: {s1_decided_side} outcome...")
                                        try:
                                            from py_clob_client_v2 import MarketOrderArgsV2
                                            token_id = market["up_id"] if s1_decided_side == "UP" else market["down_id"]
                                            resp = clob_client.create_and_post_market_order(
                                                order_args=MarketOrderArgsV2(
                                                    token_id=token_id, amount=sprint_stake, side="BUY"
                                                )
                                            )
                                            print(f"  ✅ [SPRINT] Live order response: {resp}")
                                        except Exception as e:
                                            print(f"  ❌ [SPRINT] Failed to place order: {e}")
                                            s1_decided_side = None
                                            s1_entry_price = None

                                    if s1_decided_side is not None:
                                        payout = sprint_stake / s1_entry_price
                                        print(
                                            f"\n  ┌──────────────────────────────────────────────────────────┐"
                                            f"\n  │  🎯 {order_msg:<20}  →  {s1_decided_side:<4}  @ ${s1_entry_price:.4f}  (T-{mark}s) │"
                                            f"\n  │  Stake: ${sprint_stake:.2f}   Payout: ${payout:.4f}  Profit: +${payout-sprint_stake:.4f}       │"
                                            f"\n  └──────────────────────────────────────────────────────────┘"
                                        )

                    # ── Phase 2: Safe Compounding Mode (50/50 Split) ──
                    else:
                        # Streak 1 (All-Rules Guarded)
                        if s1_decided_side is None and last_clear_signal is not None:
                            if abs(last_price - ptb) >= MIN_MOVE_REQUIRED and last_clear_signal == current_dir:
                                sig_ask = up_ask if last_clear_signal == "UP" else down_ask
                                if sig_ask is not None:
                                    if sig_ask > MAX_EARLY_PRICE:
                                        print(f"\n  ⚠️ [S1 OFF-PEAK] Skipping bet: price is too expensive (${sig_ask:.4f} > ${MAX_EARLY_PRICE:.2f}).")
                                        continue

                                    s1_decided_side = last_clear_signal
                                    s1_entry_price  = sig_ask
                                    results[-1]["bet_placed"] = True

                                    order_msg = "PAPER BET [S1]"
                                    if clob_client is not None:
                                        order_msg = "LIVE BET [S1]"
                                        print(f"\n  🚀 [S1] PLACING LIVE ORDER: {s1_decided_side} outcome...")
                                        try:
                                            from py_clob_client_v2 import MarketOrderArgsV2
                                            token_id = market["up_id"] if s1_decided_side == "UP" else market["down_id"]
                                            resp = clob_client.create_and_post_market_order(
                                                order_args=MarketOrderArgsV2(
                                                    token_id=token_id, amount=streak_1_stake, side="BUY"
                                                )
                                            )
                                            print(f"  ✅ [S1] Live order response: {resp}")
                                        except Exception as e:
                                            print(f"  ❌ [S1] Failed to place order: {e}")
                                            s1_decided_side = None
                                            s1_entry_price = None

                                    if s1_decided_side is not None:
                                        payout = streak_1_stake / s1_entry_price
                                        print(
                                            f"\n  ┌──────────────────────────────────────────────────────────┐"
                                            f"\n  │  🎯 {order_msg:<15}  →  {s1_decided_side:<4}  @ ${s1_entry_price:.4f}  (T-{mark}s)      │"
                                            f"\n  │  Stake: ${streak_1_stake:.2f}   Payout: ${payout:.4f}  Profit: +${payout-streak_1_stake:.4f}           │"
                                            f"\n  └──────────────────────────────────────────────────────────┘"
                                        )

                        # Streak 2 (Close-Only: T-12s to T-5s)
                        if s2_decided_side is None and (5 <= mark <= 12) and last_clear_signal is not None:
                            if abs(last_price - ptb) >= MIN_MOVE_REQUIRED and last_clear_signal == current_dir:
                                sig_ask = up_ask if last_clear_signal == "UP" else down_ask
                                if sig_ask is not None:
                                    if sig_ask > MAX_EARLY_PRICE:
                                        print(f"\n  ⚠️ [S2 OFF-PEAK] Skipping bet: price is too expensive (${sig_ask:.4f} > ${MAX_EARLY_PRICE:.2f}).")
                                        continue

                                    s2_decided_side = last_clear_signal
                                    s2_entry_price  = sig_ask
                                    results[-1]["bet_placed"] = True

                                    order_msg = "PAPER BET [S2]"
                                    if clob_client is not None:
                                        order_msg = "LIVE BET [S2]"
                                        print(f"\n  🚀 [S2] PLACING LIVE ORDER: {s2_decided_side} outcome...")
                                        try:
                                            from py_clob_client_v2 import MarketOrderArgsV2
                                            token_id = market["up_id"] if s2_decided_side == "UP" else market["down_id"]
                                            resp = clob_client.create_and_post_market_order(
                                                order_args=MarketOrderArgsV2(
                                                    token_id=token_id, amount=streak_2_stake, side="BUY"
                                                )
                                            )
                                            print(f"  ✅ [S2] Live order response: {resp}")
                                        except Exception as e:
                                            print(f"  ❌ [S2] Failed to place order: {e}")
                                            s2_decided_side = None
                                            s2_entry_price = None

                                    if s2_decided_side is not None:
                                        payout = streak_2_stake / s2_entry_price
                                        print(
                                            f"\n  ┌──────────────────────────────────────────────────────────┐"
                                            f"\n  │  🎯 {order_msg:<15}  →  {s2_decided_side:<4}  @ ${s2_entry_price:.4f}  (T-{mark}s)      │"
                                            f"\n  │  Stake: ${streak_2_stake:.2f}   Payout: ${payout:.4f}  Profit: +${payout-streak_2_stake:.4f}           │"
                                            f"\n  └──────────────────────────────────────────────────────────┘"
                                        )

        time.sleep(0.1)

    print()
    return results, s1_decided_side, s1_entry_price, s2_decided_side, s2_entry_price, last_price

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

def print_summary(results, w_start, w_end, ptb, last_price, s1_side, s1_price, s2_side, s2_price):
    net = last_price - ptb
    direction = "UP ▲" if net > 0 else "DOWN ▼"

    print(f"\n  {'═'*72}")
    print(f"  ⏰ WINDOW CLOSED : {fmt_win(w_start)}")
    print(f"  📌 Price to Beat  : ${ptb:,.2f}")
    print(f"  🏁 Final Price    : ${last_price:,.2f}  (next window's PTB)")
    print(f"  📊 Net move       : {net:>+.2f}   →  {direction}")
    if s1_side:
        print(f"  🎯 Bet [Streak 1] : {s1_side} @ ${s1_price:.4f}")
    if s2_side:
        print(f"  🎯 Bet [Streak 2] : {s2_side} @ ${s2_price:.4f}")
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

def main():
    global sprint_stake, sprint_wins, streak_1_stake, streak_1_wins, streak_2_stake, streak_2_wins

    mode_str = "LIVE BET" if POLYMARKET_LIVE_TRADING else "PAPER BET"
    print("\n" + "═"*72)
    print(f"  🤖 Off-Peak 5-Min Hybrid Sprint Bot  [{mode_str}]")
    print("═"*72)

    clob_client = None
    if POLYMARKET_LIVE_TRADING:
        print("  ⚠️  LIVE TRADING ENABLED! Initializing Polymarket CLOB Client...")
        try:
            from py_clob_client_v2 import ClobClient, ApiCreds
            from eth_account import Account
            
            eoa_address = Account.from_key(POLYMARKET_PRIVATE_KEY).address
            sig_type = 0
            funder_addr = None
            if POLYMARKET_ADDRESS and POLYMARKET_ADDRESS.lower() != eoa_address.lower():
                sig_type = 3
                funder_addr = POLYMARKET_ADDRESS

            creds = ApiCreds(
                api_key=POLYMARKET_API_KEY,
                api_secret=POLYMARKET_API_SECRET,
                api_passphrase=POLYMARKET_API_PASSPHRASE
            )
            clob_client = ClobClient(
                host=CLOB_HOST, chain_id=137, key=POLYMARKET_PRIVATE_KEY, creds=creds, signature_type=sig_type, funder=funder_addr
            )
            print("  ✅ CLOB Client initialized.")
        except Exception as e:
            print(f"  ❌ Error initializing CLOB client: {e}")
            sys.exit(1)

    ws = WSFeed()
    ws.start()

    for _ in range(40):
        if ws.latest():
            break
        time.sleep(0.5)
    tick = ws.latest()
    if not tick:
        print("  ❌ No WS data — check connection.")
        sys.exit(1)
    btc_p, _ = tick
    print(f"  ✅ WS connected — BTC/USD: ${btc_p:,.2f}")

    state_loaded = load_state()

    if POLYMARKET_LIVE_TRADING and clob_client is not None:
        bal = get_live_balance(clob_client)
        if bal is not None:
            print(f"  💰 Startup balance verification: ${bal:.2f} pUSD. Adjusting stakes...")
            if bal >= 10.00:
                split_stake = max(1.00, round((bal - 0.10) / 2.0, 2))
                streak_1_stake = split_stake
                streak_2_stake = split_stake
                save_state()
            elif bal < 10.00 and (sprint_stake == 1.00 or bal > sprint_stake + 2.00):
                sprint_stake = max(1.00, round(bal - 0.05, 2))
                save_state()
    else:
        save_state()

    print("═"*72 + "\n")

    while True:
        try:
            # 🛑 AUTO-CUTOFF CHECK: Stop immediately at 4:00 AM GMT (UTC)
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            if now_utc.hour >= AUTO_CUTOFF_HOUR_GMT and now_utc.hour < 12:
                print("\n" + "═"*72)
                print(f"  🛑 4:00 AM GMT AUTO-CUTOFF REACHED ({now_utc.strftime('%H:%M:%S GMT')})")
                print(f"  Stopping bot automatically. All funds are safe in your wallet!")
                print("═"*72 + "\n")
                sys.exit(0)

            now       = time.time()
            w_s       = win_start(now)
            w_e       = win_end(now)
            secs_into = now - w_s

            if POLYMARKET_LIVE_TRADING and clob_client is not None:
                bal = get_live_balance(clob_client)
                if bal is not None:
                    phase = 1 if bal < 10.00 else 2
                else:
                    phase = 1 if (sprint_stake + 0.05) < 10.00 else 2
            else:
                phase = 1 if sprint_stake < 10.00 else 2

            if secs_into > 10:
                sleep_secs = w_e - time.time() + 0.5
                print(f"  ⏰ Mid-window start ({secs_into:.0f}s into window) — sleeping {sleep_secs:.1f}s until next window...")
                time.sleep(max(0, sleep_secs))
                now = time.time()
                w_s = win_start(now)
                w_e = w_s + WINDOW_SECS

            slug = slug_for(w_s)
            print(f"  ════════════════════════════════════════════════════════════════════════")
            print(f"  🆕 STARTING NEW OFF-PEAK CYCLE")
            print(f"  Current time   : {fmt(now)}")
            print(f"  Current window : {fmt_win(w_s)}")
            if phase == 1:
                print(f"  Current Mode   : PHASE 1 (Sprint Mode — 100% Wallet)")
                print(f"    - Sprint Stake : ${sprint_stake:.2f} (Wins: {sprint_wins})")
            else:
                print(f"  Current Mode   : PHASE 2 (Safe Compounding 50/50 Split)")
                print(f"    - Streak 1 Stake   : ${streak_1_stake:.2f} pUSD ({streak_1_wins}/{STREAK_WIN_CAP} Wins)")
                print(f"    - Streak 2 Stake   : ${streak_2_stake:.2f} pUSD ({streak_2_wins}/{STREAK_WIN_CAP} Wins)")
            print(f"  Bet window     : T-{BET_WINDOW_START}s → T-{BET_WINDOW_END}s")
            print(f"  Max Price Cap  : ${MAX_EARLY_PRICE:.2f}  |  Min Distance: ${MIN_MOVE_REQUIRED:.2f}")
            print(f"  ════════════════════════════════════════════════════════════════════════\n")

            print(f"  📡 Window: {fmt_win(w_s)}")
            print(f"  Waiting for first tick (Price to Beat)...")

            btc_ptb = None
            deadline = time.time() + 30
            while time.time() < deadline:
                result = ws.price_at_or_after(w_s)
                if result:
                    btc_ptb, ptb_ts_ms = result
                    offset_sec = (ptb_ts_ms / 1000.0) - w_s
                    print(f"  📌 PRICE TO BEAT : ${btc_ptb:,.2f}  (+{offset_sec:.1f}s after boundary)\n")
                    break
                time.sleep(0.1)

            if btc_ptb is None:
                print("  ❌ Could not capture PTB — skipping window.\n")
                time.sleep(max(10, w_e - time.time()))
                continue

            print(f"  🔍 Resolving market {slug}...")
            market = None
            for _ in range(20):
                try:
                    market = resolve_market(slug)
                    if market:
                        print(f"  📋 {market['title']}\n")
                        break
                except Exception:
                    pass
                time.sleep(2)

            if not market:
                print("  ❌ Could not resolve market token IDs — skipping window.\n")
                time.sleep(max(10, w_e - time.time()))
                continue

            wake_at   = w_e - WAKE_UP_BEFORE
            wait_secs = wake_at - time.time()
            if wait_secs > 0:
                print(f"  ⏳ Sleeping {wait_secs:.0f}s — will wake up at T-{WAKE_UP_BEFORE}s ({fmt(wake_at)})...\n")
                time.sleep(wait_secs)

            if POLYMARKET_LIVE_TRADING and clob_client is not None:
                bal = get_live_balance(clob_client)
                if bal is not None:
                    phase = 1 if bal < 10.00 else 2
                    if phase == 1:
                        sprint_stake = max(1.00, round(bal - 0.05, 2))
                    else:
                        split_stake = max(1.00, round((bal - 0.10) / 2.0, 2))
                        if streak_1_wins == 0:
                            streak_1_stake = split_stake
                        if streak_2_wins == 0:
                            streak_2_stake = split_stake
                    save_state()

            results, s1_side, s1_price, s2_side, s2_price, last_price = run_probe_phase(
                ws, btc_ptb, w_e, market, clob_client=clob_client, phase=phase
            )

            if phase == 1:
                print_summary(results, w_s, w_e, btc_ptb, last_price, s1_side, s1_price, None, None)
            else:
                print_summary(results, w_s, w_e, btc_ptb, last_price, s1_side, s1_price, s2_side, s2_price)

            actual_direction = "UP" if (last_price > btc_ptb) else "DOWN"

            if phase == 1:
                if s1_side and s1_price:
                    won = (s1_side == actual_direction)
                    s_old = sprint_stake
                    if won:
                        sprint_wins += 1
                        sprint_stake = round(s_old / s1_price, 2)
                        print(f"  💰 [SPRINT WIN] Win #{sprint_wins}! Payout rolled over: ${sprint_stake:.2f} pUSD")
                    else:
                        print("  ❌ [SPRINT LOSS] Safety reset: Stake dropping back to $1.00 pUSD.")
                        sprint_stake = 1.00
                        sprint_wins = 0

                    save_state()
                    threading.Thread(target=settle, args=(slug, s1_side, s1_price, s_old, "SPRINT"), daemon=True).start()

            else:
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
                            streak_1_stake = max(1.00, round((bal - 0.10) / 2.0, 2)) if bal else 1.00
                            streak_1_wins = 0
                    else:
                        print(f"  ❌ [S1 LOSS] Safety reset: Resetting streak 1...")
                        bal = get_live_balance(clob_client) if clob_client else None
                        streak_1_stake = max(1.00, round((bal - 0.10) / 2.0, 2)) if bal else 1.00
                        streak_1_wins = 0
                    
                    save_state()
                    threading.Thread(target=settle, args=(slug, s1_side, s1_price, s1_old, "S1"), daemon=True).start()

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
                            streak_2_stake = max(1.00, round((bal - 0.10) / 2.0, 2)) if bal else 1.00
                            streak_2_wins = 0
                    else:
                        print(f"  ❌ [S2 LOSS] Safety reset: Resetting streak 2...")
                        bal = get_live_balance(clob_client) if clob_client else None
                        streak_2_stake = max(1.00, round((bal - 0.10) / 2.0, 2)) if bal else 1.00
                        streak_2_wins = 0
                    
                    save_state()
                    threading.Thread(target=settle, args=(slug, s2_side, s2_price, s2_old, "S2"), daemon=True).start()

            sleep_until_next = w_e - time.time() + 0.5
            if sleep_until_next > 0:
                time.sleep(sleep_until_next)

        except KeyboardInterrupt:
            print("\n  Stopped by user.")
            sys.exit(0)
        except Exception as e:
            print(f"  ❌ Error in main loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
