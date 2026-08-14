#!/usr/bin/env python3
"""
latency_arb_bot.py — Black-Scholes Latency Arbitrage Bot for Polymarket BTC 5-Min Markets.
Prices the UP/DOWN binary contracts in real-time and executes trades when the Polymarket
order book lags behind the fair mathematical probability.
"""

import os
import sys
import time
import json
import math
import ssl
import datetime
import threading
import requests
import websocket
from dotenv import load_dotenv

# Load env variables
load_dotenv()

POLYMARKET_LIVE_TRADING = os.getenv("POLYMARKET_LIVE_TRADING", "False").lower() in ("true", "1", "yes")
POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS")
POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY")
POLYMARKET_API_SECRET = os.getenv("POLYMARKET_API_SECRET")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE")
POLYMARKET_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY")

CLOB_HOST = "https://clob.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"
LIVE_WS_URL = "wss://ws-live-data.polymarket.com/"
WINDOW_SECS = 300

# Strategy Config
MIN_EDGE = 0.15             # Minimum mathematical edge required to bet (15%)
MIN_BTC_MOVE = 5.0          # Minimum BTC move from PTB in dollars before considering trade
MIN_ASK_PRICE = 0.04        # $0.04 per share (5 shares = $0.20 total)
MAX_ASK_PRICE = 0.06        # $0.06 per share (5 shares = $0.30 + $0.02 fee = $0.32 total, fits $0.352 balance)
STAKE_USD = 0.35            # Micro stake budget
BTC_VOLATILITY = 0.50       # Annualized volatility of Bitcoin (50%)
PROBE_INTERVAL = 1.5        # Seconds between order book checks to avoid rate limits

# ── SSL Context ─────────────────────────────────────────────────────────────────
def make_ssl_ctx():
    ctx = ssl.create_default_context()
    for cert_path in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(cert_path):
            ctx.load_verify_locations(cert_path)
            break
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

# ── Math: Black-Scholes Binary Option Probability ────────────────────────────────
def normal_cdf(x):
    """Cumulative distribution function for standard normal distribution."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def calculate_true_probability(S, K, T_sec, sigma=BTC_VOLATILITY):
    """
    Calculates probability that S_T >= K at expiration using Black-Scholes d2.
    S: Current BTC spot price
    K: Price to Beat (PTB)
    T_sec: Seconds remaining until window close
    sigma: Annualized volatility
    """
    if T_sec <= 0:
        return 1.0 if S >= K else 0.0
    
    # Convert seconds remaining to years
    T_years = T_sec / 31536000.0
    
    try:
        denom = sigma * math.sqrt(T_years)
        d2 = (math.log(S / K) - 0.5 * (sigma ** 2) * T_years) / denom
        return normal_cdf(d2)
    except ZeroDivisionError:
        return 1.0 if S >= K else 0.0
    except ValueError:
        return 0.5

# ── Polymarket Official Chainlink Price Websocket ──────────────────────────────
class PolymarketChainlinkWSFeed:
    def __init__(self):
        self._price = None
        self._ts_ms = None
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._stopped = False
        self._ws_app = None

    def start(self):
        ssl_ctx = make_ssl_ctx()

        def on_open(ws):
            ws.send(json.dumps({
                "action": "subscribe",
                "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}]
            }))

        def on_message(ws, raw):
            if not raw:
                return
            try:
                msg = json.loads(raw)
                if msg.get("topic") != "crypto_prices_chainlink":
                    return
                p = msg.get("payload", {})
                if p.get("symbol") != "btc/usd":
                    return
                val = p.get("value")
                ts = p.get("timestamp")
                if val is not None and ts is not None:
                    with self._lock:
                        self._price = float(val)
                        self._ts_ms = int(ts)
                        self._ready.set()
            except Exception:
                pass

        def on_close(ws, close_status_code, close_msg):
            if not self._stopped:
                time.sleep(2)
                self.start()

        def on_error(ws, err):
            pass

        self._ws_app = websocket.WebSocketApp(
            LIVE_WS_URL,
            header={"User-Agent": "Mozilla/5.0"},
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error
        )
        threading.Thread(
            target=lambda: self._ws_app.run_forever(sslopt={"context": ssl_ctx}, ping_interval=20, ping_timeout=10),
            daemon=True
        ).start()
        self._ready.wait(timeout=15)

    def latest(self):
        with self._lock:
            return (self._price, self._ts_ms) if self._price is not None else None

    def stop(self):
        self._stopped = True
        if self._ws_app:
            self._ws_app.close()

# ── Polymarket Helpers ──────────────────────────────────────────────────────────
def resolve_market_clob_details(market_hash):
    try:
        r = requests.get(f"{CLOB_HOST}/markets/{market_hash}", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def resolve_market_by_slug(slug):
    try:
        r = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=5)
        if r.status_code == 200:
            evts = r.json()
            if evts and "markets" in evts[0] and evts[0]["markets"]:
                m = evts[0]["markets"][0]
                tids = json.loads(m.get("clobTokenIds") or "[]")
                outs = [str(o).lower() for o in json.loads(m.get("outcomes") or "[]")]
                up_id = dn_id = None
                for i, o in enumerate(outs):
                    if o in ("up", "yes"): up_id = tids[i]
                    elif o in ("down", "no"): dn_id = tids[i]
                if not up_id: up_id = tids[0]
                if not dn_id: dn_id = tids[1]
                return {
                    "slug": slug,
                    "title": m.get("question", slug),
                    "up_id": up_id,
                    "down_id": dn_id,
                    "condition_id": m.get("conditionId")
                }
    except Exception:
        pass
    return None

def probe_best_asks(up_id, down_id):
    """Fetch best asks for both UP and DOWN tokens from Polymarket."""
    up_ask = down_ask = None
    try:
        r_up = requests.get(f"{CLOB_HOST}/book", params={"token_id": up_id}, timeout=2)
        if r_up.status_code == 200:
            asks = r_up.json().get("asks", [])
            if asks:
                up_ask = float(min(asks, key=lambda a: float(a["price"]))["price"])
        
        r_down = requests.get(f"{CLOB_HOST}/book", params={"token_id": down_id}, timeout=2)
        if r_down.status_code == 200:
            asks = r_down.json().get("asks", [])
            if asks:
                down_ask = float(min(asks, key=lambda a: float(a["price"]))["price"])
    except Exception:
        pass
    return up_ask, down_ask

# ── Settlement Polling ──────────────────────────────────────────────────────────
def settle_virtual_trade(market_hash, decided_side, entry_price, stake_usd, slug):
    print(f"\n  [WAIT] Polling resolution for {slug}...")
    for _ in range(60):
        time.sleep(5)
        details = resolve_market_clob_details(market_hash)
        if details:
            tokens = details.get("tokens", [])
            closed = details.get("closed", False)
            has_winner = any(tok.get("winner") is not None for tok in tokens)
            if closed or has_winner:
                winner_outcome = None
                for tok in tokens:
                    if tok.get("winner") is True or tok.get("price") == 1:
                        winner_outcome = tok.get("outcome")
                        break
                if winner_outcome:
                    won = (decided_side.lower() == winner_outcome.lower())
                    payout = (stake_usd / entry_price) if won else 0.0
                    pnl = payout - stake_usd
                    status_str = "WIN  (OK)" if won else "LOSS (FAIL)"
                    print(f"\n  " + "="*48)
                    print(f"  [RESULT] : {status_str}")
                    print(f"  [BET]    : {decided_side} @ ${entry_price:.4f}")
                    print(f"  [OUTCOME]: {winner_outcome}")
                    print(f"  [P&L]    : {pnl:+.4f} USDC (Stake: ${stake_usd:.2f})")
                    print(f"  " + "="*48 + "\n")
                    return
    print(f"  [WARN] Market resolution timed out for {slug}.")

# ── Main Arb Loop ───────────────────────────────────────────────────────────────
def main():
    print(f"\n" + "="*72)
    print(f"  BLACK-SCHOLES LATENCY ARBITRAGE BOT")
    print(f"  Mode: " + ("LIVE TRADING" if POLYMARKET_LIVE_TRADING else "PAPER TRADING (MOCK FILLS)"))
    print(f"  Min Edge Required: {MIN_EDGE * 100:.1f}% (${MIN_EDGE:.2f} difference)")
    print(f"  Annualized Volatility (sigma): {BTC_VOLATILITY * 100:.1f}%")
    print(f"  Order Book Probe Interval: {PROBE_INTERVAL}s")
    print(f"="*72 + "\n")

    clob_client = None
    if POLYMARKET_LIVE_TRADING:
        if not all([POLYMARKET_ADDRESS, POLYMARKET_API_KEY, POLYMARKET_API_SECRET, POLYMARKET_API_PASSPHRASE, POLYMARKET_PRIVATE_KEY]):
            print("  [ERROR] Live credentials missing in .env! Exiting.")
            sys.exit(1)
        try:
            from py_clob_client_v2 import ClobClient, ApiCreds
            creds = ApiCreds(
                api_key=POLYMARKET_API_KEY,
                api_secret=POLYMARKET_API_SECRET,
                api_passphrase=POLYMARKET_API_PASSPHRASE
            )
            clob_client = ClobClient(
                host=CLOB_HOST, chain_id=137, key=POLYMARKET_PRIVATE_KEY, creds=creds, signature_type=3, funder=POLYMARKET_ADDRESS
            )
            print("  [SUCCESS] CLOB client initialized for live execution.\n")
        except Exception as e:
            print(f"  [ERROR] Error initializing CLOB client: {e}. Exiting.")
            sys.exit(1)

    # ── Initialize Price Feed ──────────────────────────────────────────────────
    feed = PolymarketChainlinkWSFeed()
    print("  Connecting to Polymarket Chainlink BTC/USD Price Feed...")
    feed.start()

    # Wait for first tick
    for _ in range(20):
        if feed.latest():
            break
        time.sleep(0.5)
    
    tick = feed.latest()
    if not tick:
        print("  [ERROR] Failed to connect to Polymarket Chainlink WebSocket. Exiting.")
        sys.exit(1)
    print(f"  [SUCCESS] Polymarket Chainlink WS Connected. Spot BTC: ${tick[0]:,.2f}\n")

    while True:
        try:
            now = time.time()
            w_s = int(now // WINDOW_SECS) * WINDOW_SECS
            w_e = w_s + WINDOW_SECS
            secs_into = now - w_s
            remaining = w_e - now
            slug = f"btc-updown-5m-{w_s}"

            print(f"\n" + "="*72)
            print(f"  [NEW] STARTING CYCLE: {slug}")
            print(f"  Window Time    : {datetime.datetime.fromtimestamp(w_s).strftime('%H:%M:%S')} UTC -> {datetime.datetime.fromtimestamp(w_e).strftime('%H:%M:%S')} UTC")
            print(f"  " + "="*72 + "\n")

            # If started mid-window, wait until next boundary
            if secs_into > 10:
                sleep_secs = remaining + 0.5
                print(f"  [WARN] Started mid-window ({int(secs_into)}s in). Sleeping {int(sleep_secs)}s until next boundary...")
                time.sleep(max(0, sleep_secs))
                continue

            # Fetch the Price to Beat (PTB) = first tick at boundary
            print("  Waiting for boundary tick to capture Price to Beat (PTB)...")
            ptb = None
            for _ in range(100):
                tick = feed.latest()
                if tick and tick[1] >= w_s * 1000:
                    ptb = tick[0]
                    break
                time.sleep(0.1)

            if not ptb:
                # Fallback to current price
                tick = feed.latest()
                ptb = tick[0]
            print(f"  [PTB] PRICE TO BEAT (K): ${ptb:,.2f}\n")

            # Resolve market details
            market = None
            print(f"  Resolving market condition IDs for {slug}...")
            for _ in range(20):
                market = resolve_market_by_slug(slug)
                if market:
                    break
                time.sleep(0.5)

            if not market:
                print("  [ERROR] Could not resolve market IDs. Skipping cycle.")
                time.sleep(remaining)
                continue
            
            print(f"  [INFO] Question: {market['title']}")
            print(f"  UP token ID : {market['up_id']}")
            print(f"  DOWN token ID: {market['down_id']}\n")

            # Active scanning phase (T-240s to T-20s)
            print(f"  [SCAN] Active Scanning Mode Started (T-240s to T-20s)...")
            print(f"  {'T-REM':>5} | {'SPOT BTC':>10} | {'PTB DIFF':>9} | {'P(UP)':>6} | {'P(DN)':>6} | {'UP ASK':>6} | {'DN ASK':>6} | STATUS")
            print(f"  {'-'*85}")

            last_probe_time = 0
            executed_trade = False

            while True:
                curr_t = time.time()
                t_rem = w_e - curr_t

                # Stop scanning at T-20s due to liquidity fade
                if t_rem < 20:
                    print(f"\n  [WAIT] T-20s reached. Scanning suspended for this window.")
                    break
                
                if executed_trade:
                    time.sleep(1)
                    continue

                tick = feed.latest()
                if not tick:
                    time.sleep(0.1)
                    continue

                btc_price = tick[0]
                diff = btc_price - ptb
                
                # Calculate True Probabilities using Black-Scholes formula
                p_up = calculate_true_probability(btc_price, ptb, t_rem, BTC_VOLATILITY)
                p_down = 1.0 - p_up

                # Read Order book asks at periodic intervals
                if curr_t - last_probe_time >= PROBE_INTERVAL:
                    last_probe_time = curr_t
                    up_ask, down_ask = probe_best_asks(market["up_id"], market["down_id"])

                    if up_ask is not None and down_ask is not None:
                        edge_up = p_up - up_ask
                        edge_dn = p_down - down_ask

                        up_str = f"${up_ask:.4f}"
                        dn_str = f"${down_ask:.4f}"
                        
                        # Print status tick line
                        print(f"  T-{int(t_rem):>3}s | ${btc_price:>9,.2f} | {diff:>+8.2f} | {p_up:>5.1%} | {p_down:>5.1%} | {up_str:>6} | {dn_str:>6} | Scanning")

                        # Check for arbitrage buy signal (UP)
                        if abs(diff) < MIN_BTC_MOVE:
                            print(f"  T-{int(t_rem):>3}s | ${btc_price:>9,.2f} | {diff:>+8.2f} | {p_up:>5.1%} | {p_down:>5.1%} | {up_str:>6} | {dn_str:>6} | [WAIT] BTC move ${abs(diff):.2f} < ${MIN_BTC_MOVE:.0f} min")
                            time.sleep(0.1)
                            continue

                        if edge_up >= MIN_EDGE and MIN_ASK_PRICE <= up_ask <= MAX_ASK_PRICE:
                            executed_trade = True
                            payout = STAKE_USD / up_ask
                            print(f"\n  [SIGNAL] ARBITRAGE SIGNAL DETECTED: UP contract is underpriced!")
                            print(f"  [PROB] True Probability : {p_up:.1%}")
                            print(f"  [INFO] Polymarket Ask   : ${up_ask:.4f}")
                            print(f"  [EDGE] Mathematical Edge: {edge_up * 100:+.1f}%")

                            if POLYMARKET_LIVE_TRADING and clob_client is not None:
                                print(f"  [LIVE] Placing 5-share limit buy order for UP @ ${up_ask:.4f} (Total: ${5.0 * up_ask:.2f})...")
                                try:
                                    from py_clob_client_v2 import OrderArgsV2, OrderType, Side
                                    resp = clob_client.create_and_post_order(
                                        order_args=OrderArgsV2(token_id=market["up_id"], price=up_ask, size=5.0, side=Side.BUY),
                                        order_type=OrderType.GTC
                                    )
                                    print(f"  [SUCCESS] Filled! Order ID: {resp.get('orderID')}")
                                except Exception as e:
                                    print(f"  [ERROR] Order failed: {e}")
                            else:
                                print(f"  ┌──────────────────────────────────────────────────────────┐")
                                print(f"  │  🎯 PAPER ARBITRAGE BOUGHT  →  UP    @ ${up_ask:.4f}  (T-{int(t_rem)}s)       │")
                                print(f"  │  Stake: ${STAKE_USD:.2f}   Payout: ${payout:.4f}  Profit: +${payout-STAKE_USD:.4f}           │")
                                print(f"  └──────────────────────────────────────────────────────────┘")

                            # Start background thread to await resolution and log final PnL
                            threading.Thread(
                                target=settle_virtual_trade,
                                args=(market["condition_id"], "UP", up_ask, STAKE_USD, slug),
                                daemon=True
                            ).start()

                        # Check for arbitrage buy signal (DOWN)
                        elif edge_dn >= MIN_EDGE and MIN_ASK_PRICE <= down_ask <= MAX_ASK_PRICE:
                            executed_trade = True
                            payout = STAKE_USD / down_ask
                            print(f"\n  [SIGNAL] ARBITRAGE SIGNAL DETECTED: DOWN contract is underpriced!")
                            print(f"  [PROB] True Probability : {p_down:.1%}")
                            print(f"  [INFO] Polymarket Ask   : ${down_ask:.4f}")
                            print(f"  [EDGE] Mathematical Edge: {edge_dn * 100:+.1f}%")

                            if POLYMARKET_LIVE_TRADING and clob_client is not None:
                                print(f"  [LIVE] Placing 5-share limit buy order for DOWN @ ${down_ask:.4f} (Total: ${5.0 * down_ask:.2f})...")
                                try:
                                    from py_clob_client_v2 import OrderArgsV2, OrderType, Side
                                    resp = clob_client.create_and_post_order(
                                        order_args=OrderArgsV2(token_id=market["down_id"], price=down_ask, size=5.0, side=Side.BUY),
                                        order_type=OrderType.GTC
                                    )
                                    print(f"  [SUCCESS] Filled! Order ID: {resp.get('orderID')}")
                                except Exception as e:
                                    print(f"  [ERROR] Order failed: {e}")
                            else:
                                print(f"  ┌──────────────────────────────────────────────────────────┐")
                                print(f"  │  🎯 PAPER ARBITRAGE BOUGHT  →  DOWN  @ ${down_ask:.4f}  (T-{int(t_rem)}s)       │")
                                print(f"  │  Stake: ${STAKE_USD:.2f}   Payout: ${payout:.4f}  Profit: +${payout-STAKE_USD:.4f}           │")
                                print(f"  └──────────────────────────────────────────────────────────┘")

                            threading.Thread(
                                target=settle_virtual_trade,
                                args=(market["condition_id"], "DOWN", down_ask, STAKE_USD, slug),
                                daemon=True
                            ).start()

                time.sleep(0.1)

            # Wait for end of current 5m window before starting new cycle
            rem_end = w_e - time.time()
            if rem_end > 0:
                time.sleep(rem_end + 2)

        except KeyboardInterrupt:
            print("\n  👋 Exiting bot loop. Goodbye!")
            feed.stop()
            sys.exit(0)
        except Exception as e:
            print(f"  [WARN] Exception in cycle loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
