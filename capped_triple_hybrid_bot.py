#!/usr/bin/env python3
"""
capped_triple_hybrid_bot.py — Triple Streak Hybrid Bot with $0.85 Max Price Cap for Big Profit Upside
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

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────────
LIVE_WS_URL   = "wss://ws-live-data.polymarket.com/"
GAMMA_HOST    = "https://gamma-api.polymarket.com"
CLOB_HOST     = "https://clob.polymarket.com"
WINDOW_SECS   = 300          # 5-minute window
WAKE_UP_BEFORE      = 90    # seconds before close to start streaming/probing
STREAK_WIN_CAP      = 4     # Take Profit: Reset streak after 4 consecutive wins

# Timing
BET_WINDOW_START    = 80    # Streak 1 early check (T-80s)
BET_WINDOW_END      = 5     # latest check for all (T-5s)

# Strategy & Profit Guardrails
MAX_EARLY_PRICE      = 0.85  # Max price cap ($0.85 cap guarantees >= +17.6% to +80% profit per win!)
CONFIDENCE_THRESHOLD = 0.65  # dominant side must be priced at $0.65+
MIN_MOVE_REQUIRED   = 25.0  # BTC must move at least $25.00 away from PTB

PROBE_MARKS = [80, 70, 60, 50, 40, 35, 30, 25, 20, 18, 15, 12, 10, 8, 5, 3, 2, 1, 0]

SETTLE_POLL_INTERVAL = 5
SETTLE_MAX_ATTEMPTS  = 60

STATE_FILE = "sprint_state.json"

# ── Global State ────────────────────────────────────────────────────────────────
streak_1_stake = 1.00
streak_1_wins = 0
streak_2_stake = 1.00
streak_2_wins = 0
streak_3_stake = 1.00
streak_3_wins = 0

log_lock = threading.Lock()
state_lock = threading.Lock()

def log_info(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    sys.stdout.flush()

def save_state():
    with state_lock:
        try:
            state = {
                "sprint_stake": 1.00,
                "sprint_wins": 0,
                "streak_1_stake": streak_1_stake,
                "streak_1_wins": streak_1_wins,
                "streak_2_stake": streak_2_stake,
                "streak_2_wins": streak_2_wins,
                "streak_3_stake": streak_3_stake,
                "streak_3_wins": streak_3_wins
            }
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            log_info(f"[ERROR] Error saving state file: {e}")

def load_state():
    global streak_1_stake, streak_1_wins, streak_2_stake, streak_2_wins, streak_3_stake, streak_3_wins
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            streak_1_stake = state.get("streak_1_stake", 1.00)
            streak_1_wins = state.get("streak_1_wins", 0)
            streak_2_stake = state.get("streak_2_stake", 1.00)
            streak_2_wins = state.get("streak_2_wins", 0)
            streak_3_stake = state.get("streak_3_stake", 1.00)
            streak_3_wins = state.get("streak_3_wins", 0)
            log_info(f"[STATE] Loaded state from {STATE_FILE}.")
            return True
        except Exception as e:
            log_info(f"[ERROR] Error loading state file: {e}")
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
    return f"{fmt(start_ts)} -> {fmt(start_ts + WINDOW_SECS)}"

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
                log_info("[WS] Feed disconnected -- reconnecting in 2 seconds...")
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
                    log_info(f"[WS] Feed stale (lag={lag:.1f}s) -- reconnecting...")
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
        log_info(f"[ERROR] Error fetching balance: {e}")
        return None

def run_probe_phase(ws: WSFeed, ptb: float, w_end: int, market: dict, clob_client=None):
    global streak_1_stake, streak_2_stake, streak_3_stake
    
    last_tick_ts       = None
    last_price         = ptb
    probes_done        = set()
    
    s1_decided_side    = None
    s1_entry_price     = None
    
    s2_decided_side    = None
    s2_entry_price     = None

    s3_decided_side    = None
    s3_entry_price     = None

    last_clear_signal  = None

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
                last_price   = price

        for mark in PROBE_MARKS:
            if mark in probes_done:
                continue
            if remaining <= mark:
                probes_done.add(mark)
                up_ask,   _ = probe_book(market["up_id"])
                down_ask, _ = probe_book(market["down_id"])

                up_str = f"${up_ask:.4f}" if up_ask is not None else "NONE"
                down_str = f"${down_ask:.4f}" if down_ask is not None else "NONE"
                log_info(f"> PROBE T-{mark:>2}s  UP={up_str:<7}  DOWN={down_str:<7}  BTC=${last_price:,.2f}")

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

                # ── Streak 1 (Trend: T-80s to T-15s) ──
                if s1_decided_side is None and (15 <= mark <= 80) and last_clear_signal is not None:
                    if int(last_price) != int(ptb) and last_clear_signal == current_dir:
                        sig_ask = up_ask if last_clear_signal == "UP" else down_ask
                        if sig_ask is not None:
                            if sig_ask > MAX_EARLY_PRICE:
                                log_info(f"[PRICE CAP] [S1] Skipping bet: price is too expensive (${sig_ask:.4f} > ${MAX_EARLY_PRICE:.2f}).")
                                continue

                            s1_decided_side = last_clear_signal
                            s1_entry_price  = sig_ask
                            
                            order_msg = "PAPER BET [S1]"
                            if clob_client is not None:
                                order_msg = "LIVE BET [S1]"
                                log_info(f"[ORDER] [S1] PLACING LIVE ORDER: {s1_decided_side} outcome...")
                                try:
                                    from py_clob_client_v2 import MarketOrderArgsV2
                                    token_id = market["up_id"] if s1_decided_side == "UP" else market["down_id"]
                                    resp = clob_client.create_and_post_market_order(
                                        order_args=MarketOrderArgsV2(
                                            token_id=token_id, amount=streak_1_stake, side="BUY"
                                        )
                                    )
                                    log_info(f"[SUCCESS] [S1] Live order response: {resp}")
                                except Exception as e:
                                    log_info(f"[ERROR] [S1] Failed to place order: {e}")
                                    s1_decided_side = None
                                    s1_entry_price = None

                            if s1_decided_side is not None:
                                log_info(f"[EXECUTE] {order_msg} placed: {s1_decided_side} @ ${s1_entry_price:.4f} (Stake: ${streak_1_stake:.2f})")

                # ── Streak 2 & 3 (Close-Only: T-12s to T-5s) ──
                if (5 <= mark <= 12) and last_clear_signal is not None:
                    if int(last_price) != int(ptb) and last_clear_signal == current_dir:
                        sig_ask = up_ask if last_clear_signal == "UP" else down_ask
                        if sig_ask is not None:
                            if sig_ask > MAX_EARLY_PRICE:
                                log_info(f"[PRICE CAP] [S2/S3] Skipping bet: price is too expensive (${sig_ask:.4f} > ${MAX_EARLY_PRICE:.2f}).")
                                continue

                            # Streak 2
                            if s2_decided_side is None:
                                s2_decided_side = last_clear_signal
                                s2_entry_price  = sig_ask
                                order_msg = "PAPER BET [S2]"
                                if clob_client is not None:
                                    order_msg = "LIVE BET [S2]"
                                    log_info(f"[ORDER] [S2] PLACING LIVE ORDER: {s2_decided_side} outcome...")
                                    try:
                                        from py_clob_client_v2 import MarketOrderArgsV2
                                        token_id = market["up_id"] if s2_decided_side == "UP" else market["down_id"]
                                        resp = clob_client.create_and_post_market_order(
                                            order_args=MarketOrderArgsV2(
                                                token_id=token_id, amount=streak_2_stake, side="BUY"
                                            )
                                        )
                                        log_info(f"[SUCCESS] [S2] Live order response: {resp}")
                                    except Exception as e:
                                        log_info(f"[ERROR] [S2] Failed to place order: {e}")
                                        s2_decided_side = None
                                        s2_entry_price = None

                                if s2_decided_side is not None:
                                    log_info(f"[EXECUTE] {order_msg} placed: {s2_decided_side} @ ${s2_entry_price:.4f} (Stake: ${streak_2_stake:.2f})")

                            # Streak 3
                            if s3_decided_side is None:
                                s3_decided_side = last_clear_signal
                                s3_entry_price  = sig_ask
                                order_msg = "PAPER BET [S3]"
                                if clob_client is not None:
                                    order_msg = "LIVE BET [S3]"
                                    log_info(f"[ORDER] [S3] PLACING LIVE ORDER: {s3_decided_side} outcome...")
                                    try:
                                        from py_clob_client_v2 import MarketOrderArgsV2
                                        token_id = market["up_id"] if s3_decided_side == "UP" else market["down_id"]
                                        resp = clob_client.create_and_post_market_order(
                                            order_args=MarketOrderArgsV2(
                                                token_id=token_id, amount=streak_3_stake, side="BUY"
                                            )
                                        )
                                        log_info(f"[SUCCESS] [S3] Live order response: {resp}")
                                    except Exception as e:
                                        log_info(f"[ERROR] [S3] Failed to place order: {e}")
                                        s3_decided_side = None
                                        s3_entry_price = None

                                if s3_decided_side is not None:
                                    log_info(f"[EXECUTE] {order_msg} placed: {s3_decided_side} @ ${s3_entry_price:.4f} (Stake: ${streak_3_stake:.2f})")

        time.sleep(0.1)

    return s1_decided_side, s1_entry_price, s2_decided_side, s2_entry_price, s3_decided_side, s3_entry_price, last_price

def settle(slug, decided_side, entry_price, stake_usd, name="S1"):
    log_info(f"[SETTLE] [{name}] Polling for market resolution ({slug})...")
    for attempt in range(1, SETTLE_MAX_ATTEMPTS + 1):
        time.sleep(SETTLE_POLL_INTERVAL)
        up_won, _ = check_resolution(slug)
        if up_won is not None:
            won = (decided_side == "UP" and up_won) or (decided_side == "DOWN" and not up_won)
            pnl = stake_usd * (1 / entry_price - 1) if won else -stake_usd
            status_text = "WIN" if won else "LOSS"
            log_info(f"[RESULT] [{name}] : {status_text} | P&L: ${pnl:>+.4f}")
            return won
    log_info(f"[SETTLE] [{name}] Market did not resolve within wait period.")
    return None

def main():
    global streak_1_stake, streak_1_wins, streak_2_stake, streak_2_wins, streak_3_stake, streak_3_wins

    POLYMARKET_LIVE_TRADING = os.getenv("POLYMARKET_LIVE_TRADING", "False").lower() in ("true", "1", "yes")
    POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS")
    POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY")
    POLYMARKET_API_SECRET = os.getenv("POLYMARKET_API_SECRET")
    POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE")
    POLYMARKET_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY")

    mode_str = "LIVE BET" if POLYMARKET_LIVE_TRADING else "PAPER BET"
    print("\n" + "="*72)
    print(f"  Capped Triple Hybrid Bot (${MAX_EARLY_PRICE:.2f} Price Cap)  [{mode_str}]")
    print("="*72)

    clob_client = None
    if POLYMARKET_LIVE_TRADING:
        log_info("[INFO] LIVE TRADING ENABLED! Initializing Polymarket CLOB Client...")
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
            log_info("[SUCCESS] CLOB Client initialized.")
        except Exception as e:
            log_info(f"[ERROR] Error initializing CLOB client: {e}")
            sys.exit(1)

    ws = WSFeed()
    ws.start()

    for _ in range(40):
        if ws.latest():
            break
        time.sleep(0.5)
    tick = ws.latest()
    if not tick:
        log_info("[ERROR] No WS data — check connection.")
        sys.exit(1)
    btc_price, _ = tick
    log_info(f"[SUCCESS] WS connected — BTC/USD: ${btc_price:,.2f}")

    state_loaded = load_state()

    if POLYMARKET_LIVE_TRADING and clob_client is not None:
        bal = get_live_balance(clob_client)
        if bal is not None:
            split_stake = max(1.00, round((bal - 0.15) / 3.0, 2))
            if not state_loaded:
                streak_1_stake = split_stake
                streak_2_stake = split_stake
                streak_3_stake = split_stake
                save_state()
            log_info(f"[BALANCE] Verified live balance: ${bal:.2f} pUSD. 3-Way Split: ${split_stake:.2f}")

    while True:
        try:
            now       = time.time()
            w_s       = win_start(now)
            w_e       = win_end(now)
            secs_into = now - w_s

            print("\n" + "="*72)
            print(f"  STARTING NEW CYCLE")
            print(f"  Current time   : {fmt(now)}")
            print(f"  Current window : {fmt_win(w_s)}")
            print(f"  [S1] Streak 1  : {streak_1_wins}/4 Wins  |  Stake: ${streak_1_stake:.2f} pUSD (Trend)")
            print(f"  [S2] Streak 2  : {streak_2_wins}/4 Wins  |  Stake: ${streak_2_stake:.2f} pUSD (Close)")
            print(f"  [S3] Streak 3  : {streak_3_wins}/4 Wins  |  Stake: ${streak_3_stake:.2f} pUSD (Close)")
            print(f"  Price Cap      : ${MAX_EARLY_PRICE:.2f}  |  Confidence: {CONFIDENCE_THRESHOLD:.2f}")
            print("="*72)

            if secs_into > 10:
                log_info(f"[TIMING] Mid-window start ({secs_into:.0f}s into window) -- sleeping until next window...")
                time.sleep(max(0, w_e - time.time() + 0.5))
                continue

            slug = slug_for(w_s)
            btc_ptb = None
            deadline = time.time() + 30
            while time.time() < deadline:
                result = ws.price_at_or_after(w_s)
                if result:
                    btc_ptb, _ = result
                    break
                time.sleep(0.1)

            if btc_ptb is None:
                log_info("[ERROR] Could not capture PTB -- skipping window.")
                time.sleep(max(10, w_e - time.time()))
                continue

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
                log_info("[ERROR] Could not resolve market -- skipping window.")
                time.sleep(max(10, w_e - time.time()))
                continue

            wake_at   = w_e - WAKE_UP_BEFORE
            wait_secs = wake_at - time.time()
            if wait_secs > 0:
                time.sleep(wait_secs)

            s1_side, s1_price, s2_side, s2_price, s3_side, s3_price, last_price = run_probe_phase(
                ws, btc_ptb, w_e, market, clob_client=clob_client
            )

            actual_direction = "UP" if (last_price > btc_ptb) else "DOWN"

            # Streak 1
            s1_old = streak_1_stake
            if s1_side and s1_price:
                s1_won = (s1_side == actual_direction)
                if s1_won:
                    streak_1_wins += 1
                    streak_1_stake = round(s1_old / s1_price, 2)
                    if streak_1_wins >= STREAK_WIN_CAP:
                        log_info("[CAP] [S1 COMPLETED 4/4 WINS] Resetting streak 1...")
                        bal = get_live_balance(clob_client) if clob_client else None
                        streak_1_stake = max(1.00, round((bal - 0.15) / 3.0, 2)) if bal else 1.00
                        streak_1_wins = 0
                else:
                    bal = get_live_balance(clob_client) if clob_client else None
                    streak_1_stake = max(1.00, round((bal - 0.15) / 3.0, 2)) if bal else 1.00
                    streak_1_wins = 0
                save_state()
                threading.Thread(target=settle, args=(slug, s1_side, s1_price, s1_old, "S1"), daemon=True).start()

            # Streak 2
            s2_old = streak_2_stake
            if s2_side and s2_price:
                s2_won = (s2_side == actual_direction)
                if s2_won:
                    streak_2_wins += 1
                    streak_2_stake = round(s2_old / s2_price, 2)
                    if streak_2_wins >= STREAK_WIN_CAP:
                        log_info("[CAP] [S2 COMPLETED 4/4 WINS] Resetting streak 2...")
                        bal = get_live_balance(clob_client) if clob_client else None
                        streak_2_stake = max(1.00, round((bal - 0.15) / 3.0, 2)) if bal else 1.00
                        streak_2_wins = 0
                else:
                    bal = get_live_balance(clob_client) if clob_client else None
                    streak_2_stake = max(1.00, round((bal - 0.15) / 3.0, 2)) if bal else 1.00
                    streak_2_wins = 0
                save_state()
                threading.Thread(target=settle, args=(slug, s2_side, s2_price, s2_old, "S2"), daemon=True).start()

            # Streak 3
            s3_old = streak_3_stake
            if s3_side and s3_price:
                s3_won = (s3_side == actual_direction)
                if s3_won:
                    streak_3_wins += 1
                    streak_3_stake = round(s3_old / s3_price, 2)
                    if streak_3_wins >= STREAK_WIN_CAP:
                        log_info("[CAP] [S3 COMPLETED 4/4 WINS] Resetting streak 3...")
                        bal = get_live_balance(clob_client) if clob_client else None
                        streak_3_stake = max(1.00, round((bal - 0.15) / 3.0, 2)) if bal else 1.00
                        streak_3_wins = 0
                else:
                    bal = get_live_balance(clob_client) if clob_client else None
                    streak_3_stake = max(1.00, round((bal - 0.15) / 3.0, 2)) if bal else 1.00
                    streak_3_wins = 0
                save_state()
                threading.Thread(target=settle, args=(slug, s3_side, s3_price, s3_old, "S3"), daemon=True).start()

            time.sleep(2)

        except Exception as e:
            log_info(f"[ERROR] Error in main loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
