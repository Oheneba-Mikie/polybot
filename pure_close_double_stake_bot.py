#!/usr/bin/env python3
"""
pure_close_rollover_bot.py - Pure Close-to-Market Always-Rollover Bot

HOW IT WORKS:
- Wakes up at T-10s before each 5-minute BTC Up/Down window close.
- Observes order books at T-8s, T-7s, T-6s (no bet yet - just watching).
- Places ONE bet at the FIRST open probe in the T-5s to T-2s window.
- At T-5s the outcome is nearly certain, but markets are still open.
- No MIN_PRICE_MOVE filter. No MAX_PRICE_LIMIT cap.
- Always bets if there is any open liquidity in the bet window.

Signal Logic:
- Whichever side (UP/DOWN) has the HIGHER ask price = our signal.
- If both sides equal or only one exists, follow live BTC vs PTB direction.
- Confidence threshold is low (0.55) so we almost always get a signal.

Rollover:
- WIN  => full payout (stake / entry_price) becomes the next stake.
- LOSS => stake resets to starting amount.
- No liquidity in bet window => skip, stake unchanged.
"""

import json
import os
import ssl
import sys
import time
import datetime
import threading
import traceback
import requests
import websocket


# ---- Onboarding --------------------------------------------------------------
def setup_dotenv_if_missing():
    env_path = ".env"
    if os.path.exists(env_path):
        return

    print("\n" + "="*72)
    print("  Pure Close Rollover Bot - Onboarding")
    print("="*72)
    print("  No .env file detected. Setting it up now.\n")

    choice = input("  Enable Live Trading? (yes/no) [Default yes]: ").strip().lower()
    live = "True" if choice in ("", "yes", "y", "true") else "False"

    if live == "False":
        with open(env_path, "w") as f:
            f.write("POLYMARKET_LIVE_TRADING=False\n")
            f.write("POLYMARKET_ADDRESS=0x0000000000000000000000000000000000000000\n")
            f.write("POLYMARKET_PRIVATE_KEY=0x0000000000000000000000000000000000000000000000000000000000000000\n")
            f.write("POLYMARKET_API_KEY=\n")
            f.write("POLYMARKET_API_SECRET=\n")
            f.write("POLYMARKET_API_PASSPHRASE=\n")
        print("\n  .env created for Paper Trading.\n" + "="*72)
        return

    pk = input("  Enter Private Key (0x...): ").strip()
    if not pk.startswith("0x"):
        pk = "0x" + pk
    if len(pk) != 66:
        print("  ERROR: Key must be 0x + 64 hex chars. Exiting.")
        sys.exit(1)

    try:
        from eth_account import Account
        eoa = Account.from_key(pk).address
        print(f"  EOA: {eoa}")
    except Exception as e:
        print(f"  ERROR: {e}"); sys.exit(1)

    proxy = None
    try:
        r = requests.get(f"https://polymarket.com/api/profile/userData?address={eoa}", timeout=10)
        if r.status_code == 200:
            proxy = r.json().get("proxyWallet")
    except Exception:
        pass

    sig_type = 0
    funder = eoa
    if proxy and proxy.lower() != eoa.lower():
        print(f"  Proxy Wallet: {proxy}")
        funder = proxy
        sig_type = 3
    else:
        print("  No proxy wallet. Using EOA.")

    try:
        from py_clob_client_v2 import ClobClient
        c = ClobClient(host="https://clob.polymarket.com", chain_id=137,
                       key=pk, signature_type=sig_type, funder=funder)
        creds = c.create_or_derive_api_key()
    except Exception as e:
        print(f"  ERROR: {e}"); sys.exit(1)

    with open(env_path, "w") as f:
        f.write(f"POLYMARKET_LIVE_TRADING=True\n")
        f.write(f"POLYMARKET_ADDRESS={funder}\n")
        f.write(f"POLYMARKET_PRIVATE_KEY={pk}\n")
        f.write(f"POLYMARKET_API_KEY={creds.api_key}\n")
        f.write(f"POLYMARKET_API_SECRET={creds.api_secret}\n")
        f.write(f"POLYMARKET_API_PASSPHRASE={creds.api_passphrase}\n")
    print("  .env saved!\n" + "="*72)


setup_dotenv_if_missing()

from dotenv import load_dotenv
load_dotenv()

POLYMARKET_LIVE_TRADING   = os.getenv("POLYMARKET_LIVE_TRADING", "False").lower() in ("true", "1", "yes")
POLYMARKET_ADDRESS        = os.getenv("POLYMARKET_ADDRESS")
POLYMARKET_API_KEY        = os.getenv("POLYMARKET_API_KEY")
POLYMARKET_API_SECRET     = os.getenv("POLYMARKET_API_SECRET")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE")
POLYMARKET_PRIVATE_KEY    = os.getenv("POLYMARKET_PRIVATE_KEY")


# ---- Config ------------------------------------------------------------------
LIVE_WS_URL          = "wss://ws-live-data.polymarket.com/"
GAMMA_HOST           = "https://gamma-api.polymarket.com"
CLOB_HOST            = "https://clob.polymarket.com"
WINDOW_SECS          = 300

WAKE_UP_BEFORE       = 10            # wake up T-10s before close
PROBE_MARKS          = [8, 7, 6, 5, 4, 3, 2]
BET_WINDOW_START     = 8             # start betting at T-8s (catch open asks before dry up)
BET_WINDOW_END       = 2             # last bet at T-2s

CONFIDENCE_THRESHOLD = 0.55          # low threshold: almost always bet
MIN_ENTRY_PRICE      = 0.15          # Never buy garbage residual asks (< 15¢)
STARTING_STAKE_USD   = 1.00

# DOUBLE STAKE MODE: Place two concurrent orders in the same window (e.g. $5 + $5)
DOUBLE_STAKE         = True          # Set True to split stake into 2 parallel orders

SETTLE_POLL_INTERVAL = 5
SETTLE_MAX_ATTEMPTS  = 60


# ---- SSL + WS ----------------------------------------------------------------
def make_ssl_ctx():
    ctx = ssl.create_default_context()
    for p in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(p):
            ctx.load_verify_locations(p)
            break
    return ctx

WS_HEADERS = {
    "Origin": "https://polymarket.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
}


# ---- Time helpers ------------------------------------------------------------
def win_start(ts=None):
    t = ts if ts is not None else time.time()
    return int(t // WINDOW_SECS) * WINDOW_SECS

def win_end(ts=None):
    return win_start(ts) + WINDOW_SECS

def slug_for(ts=None):
    return f"btc-updown-5m-{win_start(ts)}"

def fmt(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")

def fmt_win(s):
    return f"{fmt(s)} -> {fmt(s + WINDOW_SECS)}"


# ---- WS feed -----------------------------------------------------------------
class WSFeed:
    def __init__(self):
        self._price = self._ts_ms = None
        self._lock  = threading.Lock()
        self._ready = threading.Event()
        self._ws_app = None

    def start(self):
        ctx = make_ssl_ctx()

        def on_open(ws):
            ws.send(json.dumps({"action": "subscribe",
                "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "update"}]}))

        def on_message(ws, raw):
            if not raw: return
            try: msg = json.loads(raw)
            except Exception: return
            if msg.get("topic") != "crypto_prices_chainlink": return
            p = msg.get("payload", {})
            if p.get("symbol") != "btc/usd": return
            with self._lock:
                self._price = p.get("value")
                self._ts_ms = p.get("timestamp")
                self._ready.set()

        def on_close(ws, c, m):
            print("  [WS] Closed - reconnecting in 2s...")
            time.sleep(2); self.start()

        def on_error(ws, e): pass

        app = websocket.WebSocketApp(LIVE_WS_URL, header=WS_HEADERS,
            on_open=on_open, on_message=on_message,
            on_close=on_close, on_error=on_error)
        self._ws_app = app
        threading.Thread(
            target=lambda: app.run_forever(sslopt={"context": ctx}, ping_interval=20, ping_timeout=10),
            daemon=True).start()
        self._ready.wait(timeout=20)

    def latest(self):
        self._stale_check()
        with self._lock:
            return (self._price, self._ts_ms) if self._price is not None else None

    def price_at_or_after(self, ts_sec):
        self._stale_check()
        with self._lock:
            if self._ts_ms and self._price and self._ts_ms >= ts_sec * 1000:
                return self._price, self._ts_ms
        return None

    def _stale_check(self):
        with self._lock:
            if self._ts_ms and (time.time() - self._ts_ms / 1000) > 15:
                print("  [WS] Stale - reconnecting...")
                self._ts_ms = self._price = None
                if self._ws_app:
                    try: self._ws_app.close()
                    except Exception: pass


# ---- API helpers -------------------------------------------------------------
def resolve_market(slug, timeout=10):
    r = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=timeout)
    r.raise_for_status()
    evts = r.json()
    if not evts: return None
    mkt  = evts[0]["markets"][0]
    tids = json.loads(mkt.get("clobTokenIds") or "[]")
    outs = [str(o).lower() for o in json.loads(mkt.get("outcomes") or "[]")]
    up_id = dn_id = None
    for i, o in enumerate(outs):
        if o in ("up", "yes"):    up_id = tids[i]
        elif o in ("down", "no"): dn_id = tids[i]
    if not up_id: up_id = tids[0]
    if not dn_id: dn_id = tids[1]
    return {"slug": slug, "title": mkt.get("question", slug), "up_id": up_id, "down_id": dn_id}


def probe_book(token_id, timeout=2):
    try:
        r = requests.get(f"{CLOB_HOST}/book", params={"token_id": token_id}, timeout=timeout)
        r.raise_for_status()
        asks = r.json().get("asks", [])
        if not asks: return None, 0
        return float(min(asks, key=lambda a: float(a["price"]))["price"]), len(asks)
    except Exception:
        return None, 0


def check_resolution(slug):
    try:
        r = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=5)
        r.raise_for_status()
        evts = r.json()
        if not evts: return None, []
        mkt  = evts[0]["markets"][0]
        prices = [float(p) for p in json.loads(mkt.get("outcomePrices") or "[]")]
        if prices and max(prices) >= 0.99:
            return prices[0] >= 0.99, prices
        return None, prices
    except Exception:
        return None, []


def get_live_balance(client):
    try:
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
        resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        return float(resp.get("balance", 0)) / 1_000_000
    except Exception as e:
        print(f"  WARNING balance: {e}"); return None


def reconstruct_stake(client):
    try:
        from py_clob_client_v2.clob_types import TradeParams
        trades = client.get_trades(TradeParams(maker_address=POLYMARKET_ADDRESS))
        if not trades:
            print("  No prior trades. Stake: $1.00"); return STARTING_STAKE_USD
        t = trades[0]
        slug  = f"btc-updown-5m-{(int(float(t.get('match_time',0))) // 300)*300}"
        print(f"  Last trade market: {slug}")
        up_won, _ = check_resolution(slug)
        if up_won is None:
            cost = float(t.get("size", 0)) * float(t.get("price", 0))
            print(f"  Unresolved. Cost: ${cost:.2f}"); return max(STARTING_STAKE_USD, round(cost, 2))
        outcome = t.get("outcome", "").upper()
        winner  = "UP" if up_won else "DOWN"
        if outcome == winner:
            pay = float(t.get("size", 0))
            print(f"  Last trade WON. Rolling: ${pay:.2f}"); return round(pay, 2)
        else:
            print("  Last trade LOST. Fresh start: $1.00"); return STARTING_STAKE_USD
    except Exception as e:
        print(f"  WARNING reconstruct: {e}"); return STARTING_STAKE_USD


# ---- Signal ------------------------------------------------------------------
def pick_side(up_ask, dn_ask, last_price, ptb):
    """
    Pick side to bet on with strict safety rules:
    1. Never buy garbage residual asks (< 15¢). If one side is dried up (None),
       the dried-up side is the actual winner!
    2. Enforce live BTC price direction alignment to avoid orderbook mismatches.
    """
    btc_dir = "UP" if last_price >= ptb else "DOWN"

    # Case 1: Both sides have orderbook asks
    if up_ask is not None and dn_ask is not None:
        if up_ask > dn_ask and up_ask >= CONFIDENCE_THRESHOLD:
            target_side = "UP"
            target_ask = up_ask
        elif dn_ask > up_ask and dn_ask >= CONFIDENCE_THRESHOLD:
            target_side = "DOWN"
            target_ask = dn_ask
        else:
            target_side = btc_dir
            target_ask = up_ask if btc_dir == "UP" else dn_ask

        # Freshness / Direction check: must align with live BTC direction
        if target_side != btc_dir:
            print(f"  ⚠️ Signal conflict: Orderbook={target_side} vs BTC={btc_dir} -> REJECT")
            return None, None

        if target_ask is not None and target_ask >= MIN_ENTRY_PRICE:
            return target_side, target_ask
        return None, None

    # Case 2: UP side dried up (no asks) => UP is the winner!
    elif up_ask is None and dn_ask is not None:
        # DOWN is the guaranteed loser selling for ~1¢. DO NOT BUY DOWN!
        if btc_dir == "UP":
            print(f"  ⚠️ UP side dried up (0 asks) -> UP won! Rejecting DOWN ask at ${dn_ask:.4f}")
            return None, None
        return None, None

    # Case 3: DOWN side dried up (no asks) => DOWN is the winner!
    elif dn_ask is None and up_ask is not None:
        # UP is the guaranteed loser selling for ~1¢. DO NOT BUY UP!
        if btc_dir == "DOWN":
            print(f"  ⚠️ DOWN side dried up (0 asks) -> DOWN won! Rejecting UP ask at ${up_ask:.4f}")
            return None, None
        return None, None

    return None, None


# ---- Probe + bet phase -------------------------------------------------------
def run_probe_phase(ws, ptb, w_end, market, clob_client=None, stake_usd=1.00):
    """
    T-8, T-7, T-6  => OBSERVE only (no bet)
    T-5, T-4, T-3, T-2 => BET ZONE (first open probe wins)
    """
    last_tick = None
    last_price = ptb
    ticks = 0
    done  = set()
    results = []
    side = price = None

    print(f"\n  === PURE CLOSE BOT  last {WAKE_UP_BEFORE}s ===")
    print(f"  PTB     : ${ptb:,.2f}  |  Stake: ${stake_usd:.2f}")
    print(f"  OBSERVE : T-{max(PROBE_MARKS)}s to T-{BET_WINDOW_START+1}s")
    print(f"  BET     : T-{BET_WINDOW_START}s to T-{BET_WINDOW_END}s")
    print(f"  {'-'*64}")

    while True:
        now  = time.time()
        rem  = w_end - now
        if rem <= -3: break

        ws_data = ws.latest()
        if ws_data:
            pr, ts = ws_data
            if ts != last_tick:
                last_tick  = ts
                last_price = pr
                ticks += 1
                diff  = pr - ptb
                arrow = "UP" if diff > 0 else ("DN" if diff < 0 else "--")
                print(f"  tick #{ticks:>3}  {fmt(ts/1000)}  ${pr:>10,.2f}  {arrow} {diff:>+7.2f}  ptb=${ptb:,.2f}  {int(rem):>3}s")

        for mark in PROBE_MARKS:
            if mark in done: continue
            if rem > mark:   continue
            done.add(mark)

            up_ask, n_up = probe_book(market["up_id"])
            dn_ask, n_dn = probe_book(market["down_id"])
            has_liq = (up_ask is not None or dn_ask is not None)
            in_bet  = (BET_WINDOW_END <= mark <= BET_WINDOW_START)
            phase   = "[BET ZONE]" if in_bet else "[OBSERVE] "
            st_str  = "OPEN" if has_liq else "CLOSED"
            u_str   = f"${up_ask:.4f}" if up_ask else "  NONE"
            d_str   = f"${dn_ask:.4f}" if dn_ask else "  NONE"

            print(f"\n  PROBE T-{mark:>2}s  {fmt(now)}  UP={u_str}({n_up})  DN={d_str}({n_dn})  BTC=${last_price:,.2f}  {st_str}  {phase}")

            results.append({
                "mark": mark, "ts": now, "up_ask": up_ask, "n_up": n_up,
                "down_ask": dn_ask, "n_down": n_dn, "has_liquidity": has_liq,
                "bet_placed": False, "observe_only": not in_bet,
            })

            if in_bet and side is None:
                if not has_liq:
                    print(f"  [T-{mark}s] No liquidity - skipping..."); continue

                s, ask = pick_side(up_ask, dn_ask, last_price, ptb)
                if s is None:
                    print(f"  [T-{mark}s] Cannot determine side - skipping..."); continue

                side  = s
                price = ask
                payout = stake_usd / price
                profit = payout - stake_usd
                results[-1]["bet_placed"] = True
                msg = "PAPER BET"

                if clob_client is not None:
                    msg = "LIVE BET"
                    if DOUBLE_STAKE:
                        single_stake = round(stake_usd / 2.0, 2)
                        if single_stake < 1.00: single_stake = stake_usd
                        print(f"  [T-{mark}s] 🚀 DOUBLE LIVE ORDER (2 x ${single_stake:.2f}): {side} @ ${price:.4f}...")
                        try:
                            from py_clob_client_v2 import MarketOrderArgsV2
                            tid = market["up_id"] if side == "UP" else market["down_id"]
                            resp1 = clob_client.create_and_post_market_order(
                                order_args=MarketOrderArgsV2(token_id=tid, amount=single_stake, side="BUY"))
                            print(f"  Order #1 response: {resp1}")
                            resp2 = clob_client.create_and_post_market_order(
                                order_args=MarketOrderArgsV2(token_id=tid, amount=single_stake, side="BUY"))
                            print(f"  Order #2 response: {resp2}")
                            try: sys.stdout.write("\a"); sys.stdout.flush()
                            except Exception: pass
                        except Exception as e:
                            print(f"  ERROR placing double order: {e}")
                            msg = "LIVE BET (FAILED)"
                            side = price = None
                            results[-1]["bet_placed"] = False
                            continue
                    else:
                        print(f"  [T-{mark}s] LIVE ORDER: {side} @ ${price:.4f}  stake=${stake_usd:.2f}...")
                        try:
                            from py_clob_client_v2 import MarketOrderArgsV2
                            tid = market["up_id"] if side == "UP" else market["down_id"]
                            resp = clob_client.create_and_post_market_order(
                                order_args=MarketOrderArgsV2(token_id=tid, amount=stake_usd, side="BUY"))
                            print(f"  Order response: {resp}")
                            try: sys.stdout.write("\a"); sys.stdout.flush()
                            except Exception: pass
                        except Exception as e:
                            print(f"  ERROR placing order: {e}")
                            msg = "LIVE BET (FAILED)"
                            side = price = None
                            results[-1]["bet_placed"] = False
                            continue

                tag_str = "DOUBLE STAKE" if DOUBLE_STAKE else "SINGLE STAKE"
                print(f"  +-----------------------------------------------------------+")
                print(f"  |  {msg} ({tag_str})  ->  {side}  @ ${price:.4f}  (T-{mark}s)          |")
                print(f"  |  Stake: ${stake_usd:.2f}  Payout: ${payout:.4f}  Profit: +${profit:.4f}    |")
                print(f"  +-----------------------------------------------------------+")

        time.sleep(0.1)

    if side:
        print(f"\n  Bet placed: {side} @ ${price:.4f}")
    else:
        print("\n  No bet placed (no liquidity T-5s to T-2s).")

    return results, side, price, last_price


# ---- Settlement --------------------------------------------------------------
def settle(slug, side, entry, stake):
    print(f"\n  Polling resolution: {slug}...")
    for i in range(1, SETTLE_MAX_ATTEMPTS+1):
        time.sleep(SETTLE_POLL_INTERVAL)
        up_won, prices = check_resolution(slug)
        print(f"  [settle {i}] prices={[f'{p:.4f}' for p in prices]}")
        if up_won is not None:
            actual = "UP" if up_won else "DOWN"
            won = (side == "UP" and up_won) or (side == "DOWN" and not up_won)
            pnl = stake * (1/entry - 1) if won else -stake
            print(f"  =====================================================")
            print(f"  RESULT  : {'WIN' if won else 'LOSS'}")
            print(f"  Bet     : {side}  |  Outcome: {actual}")
            print(f"  P&L     : ${pnl:>+.4f}  (stake ${stake:.2f})")
            print(f"  =====================================================\n")
            return won
    print("  WARNING: market did not resolve in time.")
    return None


# ---- Summary -----------------------------------------------------------------
def print_summary(results, w_s, w_e, ptb, last_price, side, entry, stake):
    net = last_price - ptb
    d   = "UP" if net > 0 else "DOWN"
    print(f"\n  {'='*72}")
    print(f"  WINDOW CLOSED  : {fmt_win(w_s)}")
    print(f"  Price to Beat  : ${ptb:,.2f}")
    print(f"  Final Price    : ${last_price:,.2f}  ({d} {net:>+.2f})")
    if side:
        ok = (side == "UP" and net > 0) or (side == "DOWN" and net < 0)
        print(f"  Bet            : {side} @ ${entry:.4f}  -> {'CORRECT' if ok else 'WRONG'}")
    print(f"  {'-'*72}")
    print(f"  {'T-MARK':>8}  {'TIME':>8}  {'UP ASK':>8}  {'DN ASK':>8}  PHASE       STATUS")
    print(f"  {'-'*72}")
    for r in results:
        u = f"${r['up_ask']:.4f}"   if r["up_ask"]   else "   NONE "
        d = f"${r['down_ask']:.4f}" if r["down_ask"] else "   NONE "
        st = "OPEN" if r["has_liquidity"] else "CLOSED"
        bt = "  <- BET" if r.get("bet_placed") else ""
        ph = "OBSERVE" if r.get("observe_only") else "BET ZONE"
        print(f"  T-{r['mark']:>4}s  {fmt(r['ts']):>8}  {u:>8}  {d:>8}  {ph:<10}  {st}{bt}")
    print(f"  {'='*72}\n")


# ---- Main --------------------------------------------------------------------
def main():
    mode = "LIVE TRADING" if POLYMARKET_LIVE_TRADING else "PAPER TRADING"
    print(f"\n{'='*72}")
    print(f"  PURE CLOSE-TO-MARKET ALWAYS-ROLLOVER BOT  |  {mode}")
    print(f"  Bet window: T-{BET_WINDOW_START}s -> T-{BET_WINDOW_END}s  |  No filters  |  Always rollover")
    print(f"{'='*72}\n")

    client = None
    if POLYMARKET_LIVE_TRADING:
        print("  LIVE TRADING ENABLED. Initializing CLOB Client...")
        if not all([POLYMARKET_ADDRESS, POLYMARKET_API_KEY,
                    POLYMARKET_API_SECRET, POLYMARKET_API_PASSPHRASE, POLYMARKET_PRIVATE_KEY]):
            print("  ERROR: Missing credentials in .env. Exiting."); sys.exit(1)
        if not POLYMARKET_PRIVATE_KEY.startswith("0x") or len(POLYMARKET_PRIVATE_KEY) != 66:
            print("  ERROR: Invalid private key format. Exiting."); sys.exit(1)
        try:
            from py_clob_client_v2 import ClobClient, ApiCreds
            from eth_account import Account
            eoa = Account.from_key(POLYMARKET_PRIVATE_KEY).address
            sig_type = 0; funder = None
            if POLYMARKET_ADDRESS and POLYMARKET_ADDRESS.lower() != eoa.lower():
                sig_type = 3; funder = POLYMARKET_ADDRESS
                print(f"  Proxy Wallet: {funder}  sig_type=3")
            else:
                print("  EOA wallet: sig_type=0")
            creds  = ApiCreds(api_key=POLYMARKET_API_KEY, api_secret=POLYMARKET_API_SECRET,
                              api_passphrase=POLYMARKET_API_PASSPHRASE)
            client = ClobClient(host=CLOB_HOST, chain_id=137, key=POLYMARKET_PRIVATE_KEY,
                                creds=creds, signature_type=sig_type, funder=funder)
            print("  CLOB Client OK.\n")
        except Exception as e:
            print(f"  ERROR: {e}. Exiting."); sys.exit(1)

    print("  Connecting to WS feed...")
    ws = WSFeed(); ws.start()
    for _ in range(40):
        if ws.latest(): break
        time.sleep(0.5)
    tick = ws.latest()
    if not tick:
        print("  ERROR: No WS data. Exiting."); sys.exit(1)
    btc, _ = tick
    print(f"  WS connected. BTC/USD: ${btc:,.2f}\n")

    stake = STARTING_STAKE_USD
    if POLYMARKET_LIVE_TRADING and client:
        bal = get_live_balance(client)
        if bal: print(f"  Live Balance: ${bal:.2f} pUSD")
        print("  Reconstructing streak from trade history...")
        stake = reconstruct_stake(client)
        print()
        try:
            u = input(f"  Override TOTAL starting stake (e.g. 10.00 for 2 x $5.00 orders)? [{stake:.2f}]: ").strip()
            if u: stake = float(u)
        except ValueError: pass

    single_part = round(stake / 2.0, 2)
    print(f"  Total starting stake: ${stake:.2f} pUSD  (Split into 2 x ${single_part:.2f} concurrent orders)")
    print(f"  Strategy: DOUBLE STAKE T-{BET_WINDOW_START}s->T-{BET_WINDOW_END}s | WIN rolls over | LOSS resets\n")

    while True:
        try:
            now  = time.time()
            w_s  = win_start(now)
            w_e  = win_end(now)
            into = now - w_s
            rem  = w_e - now

            print(f"\n{'='*72}")
            print(f"  NEW CYCLE  |  {fmt(now)}  |  Window: {fmt_win(w_s)}")
            print(f"  Into: {int(into)}s  |  Remaining: {int(rem)}s  |  Stake: ${stake:.2f}")
            print(f"{'='*72}\n")

            if into > 10:
                sl = w_e - time.time() + 0.5
                print(f"  Mid-window ({int(into)}s in). Sleeping {int(sl)}s...")
                time.sleep(max(0, sl))
                now = time.time(); w_s = win_start(now); w_e = w_s + WINDOW_SECS

            slug = slug_for(w_s)
            print(f"  Window: {fmt_win(w_s)}")
            print("  Waiting for Price to Beat...")
            ptb = None
            dl  = time.time() + 30
            while time.time() < dl:
                r = ws.price_at_or_after(w_s)
                if r:
                    ptb, ts = r
                    lag = int(ts/1000 - w_s)
                    print(f"  PTB: ${ptb:,.2f}  (+{lag}s)\n")
                    break
                time.sleep(0.1)
            if ptb is None:
                print("  Could not get PTB. Skipping window.")
                time.sleep(max(10, w_e - time.time())); continue

            print(f"  Resolving market: {slug}...")
            market = None
            for _ in range(20):
                try:
                    market = resolve_market(slug)
                    if market: break
                except Exception: pass
                time.sleep(2)
            if not market:
                print("  Could not resolve market. Skipping.")
                time.sleep(max(10, w_e - time.time())); continue
            print(f"  Market: {market['title']}\n")

            wake_at = w_e - WAKE_UP_BEFORE
            wait    = wake_at - time.time()
            if wait > 0:
                print(f"  Sleeping {int(wait)}s -> waking at T-{WAKE_UP_BEFORE}s ({fmt(wake_at)})...\n")
                time.sleep(wait)

            results, side, entry, last_price = run_probe_phase(
                ws, ptb, w_e, market, clob_client=client, stake_usd=stake)

            print_summary(results, w_s, w_e, ptb, last_price, side, entry, stake)

            if side and entry:
                actual = "UP" if last_price > ptb else "DOWN"
                won    = (side == actual)
                old_stake = stake
                if won:
                    stake = round(old_stake / entry, 2)
                    print(f"  WIN! Rolled over -> next stake: ${stake:.2f} pUSD\n")
                else:
                    stake = STARTING_STAKE_USD
                    print(f"  LOSS. Reset -> ${stake:.2f} pUSD\n")
                threading.Thread(target=settle, args=(slug, side, entry, old_stake), daemon=True).start()
            else:
                print("  No bet placed. Stake unchanged.\n")

            time.sleep(2)

        except Exception as e:
            print(f"\n  ERROR: {e}")
            traceback.print_exc()
            print("  Restarting in 10s...\n")
            time.sleep(10)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Stopped by user.")
