"""
================================================================================
PURE CLOSE BOT WITH PTB-DEFER GUARD (T-2s LATE STAKE)
================================================================================
Rule Overview:
- Base: Pure Close-to-Market Rollover Bot
- Addition:
    1. At T-8s to T-3s: If BTC live price is CLOSE to PTB (gap < $5.00):
       -> DO NOT STAKE. Wait for T-2s!
    2. At T-2s: Check live BTC direction vs PTB again ("UP" if BTC >= PTB else "DOWN").
       -> Stake on the NEW direction at T-2s!
    3. If BTC gap is >= $5.00 at T-8s:
       -> Stake immediately at T-8s as normal.
================================================================================
"""

import os, sys, time, json, datetime, ssl, threading, requests, traceback

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"
LIVE_WS_URL= "wss://ws-live-data.polymarket.com/"

# Configuration
POLYMARKET_LIVE_TRADING = True
CLOSE_PTB_THRESHOLD     = 5.00     # $5.00 gap threshold for deferring to T-2s
CONFIDENCE_THRESHOLD    = 0.55     # Low threshold for normal signal
MIN_ENTRY_PRICE         = 0.15     # Reject residual asks below 15¢
STARTING_STAKE_USD      = 1.00
DOUBLE_STAKE            = True     # Double stake mode (2 x parallel orders)

WAKE_UP_BEFORE   = 10
BET_WINDOW_START = 8
BET_WINDOW_END   = 2
PROBE_MARKS      = [8, 7, 6, 5, 4, 3, 2]
WINDOW_SECS      = 300
SETTLE_POLL_INTERVAL = 5
SETTLE_MAX_ATTEMPTS  = 60

# Credentials
def load_env():
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

load_env()
POLYMARKET_ADDRESS        = os.getenv("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY        = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET     = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY    = os.getenv("POLYMARKET_PRIVATE_KEY", "")

def make_ssl_ctx():
    ctx = ssl.create_default_context()
    for p in ["/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"]:
        if os.path.exists(p):
            ctx.load_verify_locations(p); break
    return ctx

WS_HEADERS = {
    "Origin": "https://polymarket.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PTBDeferBot/1.0"
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

def fmt_win(s):
    return f"{fmt(s)} -> {fmt(s + WINDOW_SECS)}"


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
            time.sleep(2); self.start()

        def on_error(ws, e): pass

        import websocket
        app = websocket.WebSocketApp(LIVE_WS_URL, header=WS_HEADERS,
            on_open=on_open, on_message=on_message,
            on_close=on_close, on_error=on_error)
        self._ws_app = app
        threading.Thread(
            target=lambda: app.run_forever(sslopt={"context": ctx}, ping_interval=20, ping_timeout=10),
            daemon=True).start()
        self._ready.wait(timeout=20)

    def latest(self):
        with self._lock:
            return (self._price, self._ts_ms) if self._price is not None else None

    def price_at_or_after(self, ts_sec):
        with self._lock:
            if self._ts_ms and self._price and self._ts_ms >= ts_sec * 1000:
                return self._price, self._ts_ms
        return None


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
        try:
            from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
        except ImportError:
            from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
        resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        return float(resp.get("balance", 0)) / 1_000_000
    except Exception as e:
        print(f"  WARNING balance: {e}"); return None


def pick_side(up_ask, dn_ask, last_price, ptb):
    btc_dir = "UP" if last_price >= ptb else "DOWN"
    if up_ask is not None and dn_ask is not None:
        if up_ask > dn_ask and up_ask >= CONFIDENCE_THRESHOLD:
            target_side, target_ask = "UP", up_ask
        elif dn_ask > up_ask and dn_ask >= CONFIDENCE_THRESHOLD:
            target_side, target_ask = "DOWN", dn_ask
        else:
            target_side, target_ask = btc_dir, (up_ask if btc_dir == "UP" else dn_ask)

        if target_side != btc_dir: return None, None
        if target_ask is not None and target_ask >= MIN_ENTRY_PRICE: return target_side, target_ask
        return None, None
    elif up_ask is None and dn_ask is not None:
        if btc_dir == "UP": return "UP", 0.99
        return None, None
    elif dn_ask is None and up_ask is not None:
        if btc_dir == "DOWN": return "DOWN", 0.99
        return None, None
    return None, None


def evaluate_ptb_defer_rule(up_ask, dn_ask, last_price, ptb, mark):
    """
    PTB Defer Rule:
    - If mark > 2 and BTC gap < $5.00: DEFER (don't stake yet)
    - At mark == 2 (T-2s): Stake on live direction!
    """
    btc_gap = abs(last_price - ptb)
    btc_dir = "UP" if last_price >= ptb else "DOWN"

    s, ask = pick_side(up_ask, dn_ask, last_price, ptb)

    if mark > 2:
        if btc_gap < CLOSE_PTB_THRESHOLD:
            return None, None, False, f"T-{mark}s: Price gap (${btc_gap:.2f}) is CLOSE to PTB (< $5.00) -> Deferring to T-2s!"
        return s, ask, (s is not None), f"T-{mark}s: Normal bet (Gap=${btc_gap:.2f} >= $5.00)"
    else:  # T-2s final stake
        final_dir = btc_dir
        final_ask = up_ask if final_dir == "UP" else dn_ask
        if final_ask is None:
            return final_dir, 0.99, True, f"T-2s FINAL STAKE: {final_dir} (Dried up / locked in)"
        if final_ask >= MIN_ENTRY_PRICE:
            return final_dir, final_ask, True, f"T-2s FINAL STAKE: {final_dir} @ ${final_ask:.4f}"
        return None, None, False, "T-2s: Final ask price below minimum (15¢)"


def run_probe_phase(ws, ptb, w_end, market, clob_client=None, stake_usd=1.00):
    last_tick = None
    last_price = ptb
    ticks = 0
    done  = set()
    results = []
    side = price = None

    print(f"\n  === PURE CLOSE BOT (PTB-DEFER GUARD)  last {WAKE_UP_BEFORE}s ===")
    print(f"  PTB         : ${ptb:,.2f}  |  Stake: ${stake_usd:.2f}")
    print(f"  PTB-Defer   : If gap < $5.00 at T-8s..T-3s -> Hold & stake NEW direction at T-2s!")
    print(f"  {'-'*68}")

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
                s, ask, approved, reason = evaluate_ptb_defer_rule(up_ask, dn_ask, last_price, ptb, mark)
                print(f"  🛡️ Rule Status: {reason}")

                if not approved or s is None:
                    continue

                side  = s
                price = ask if ask else 0.99
                single_stake = round(stake_usd / 2.0, 2) if DOUBLE_STAKE else stake_usd
                if single_stake < 1.00: single_stake = stake_usd
                payout = stake_usd / price
                profit = payout - stake_usd
                results[-1]["bet_placed"] = True

                if clob_client is not None:
                    print(f"  [T-{mark}s] 🚀 LIVE STAKE ORDER: {side} @ ${price:.4f}...")
                    try:
                        try:
                            from py_clob_client.clob_types import MarketOrderArgs
                            OrderClass = MarketOrderArgs
                        except ImportError:
                            try:
                                from py_clob_client_v2 import MarketOrderArgsV2 as OrderClass
                            except ImportError:
                                from py_clob_client import MarketOrderArgs as OrderClass
                        tid = market["up_id"] if side == "UP" else market["down_id"]
                        if DOUBLE_STAKE:
                            clob_client.create_and_post_market_order(OrderClass(token_id=tid, amount=single_stake, price=price, side="BUY"))
                            clob_client.create_and_post_market_order(OrderClass(token_id=tid, amount=single_stake, price=price, side="BUY"))
                        else:
                            clob_client.create_and_post_market_order(OrderClass(token_id=tid, amount=single_stake, price=price, side="BUY"))
                    except Exception as e:
                        print(f"  ERROR executing order: {e}")

                print(f"  +-----------------------------------------------------------+")
                print(f"  |  LIVE BET ->  {side:<4} @ ${price:.4f}  (T-{mark}s)                   |")
                print(f"  |  Stake: ${stake_usd:.2f}  Payout: ${payout:.4f}  Profit: +${profit:.4f}    |")
                print(f"  +-----------------------------------------------------------+")

        time.sleep(0.05)

    if side:
        win = poll_settlement(slug_for(w_end - WINDOW_SECS), side, price, stake_usd)
        return side, price, win
    else:
        print("\n  No bet placed. Stake unchanged.")
        return None, None, None


def poll_settlement(slug, side, entry, stake):
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


def main():
    mode = "LIVE TRADING" if POLYMARKET_LIVE_TRADING else "PAPER TRADING"
    print(f"\n{'='*72}")
    print(f"  PURE CLOSE BOT WITH PTB-DEFER GUARD  |  {mode}")
    print(f"  If gap < $5.00 at T-8s..T-3s -> Wait & stake NEW direction at T-2s!")
    print(f"{'='*72}\n")

    client = None
    if POLYMARKET_LIVE_TRADING:
        try:
            try:
                from py_clob_client.client import ClobClient
                from py_clob_client.clob_types import ApiCreds
            except ImportError:
                try:
                    from py_clob_client_v2 import ClobClient, ApiCreds
                except ImportError:
                    from py_clob_client import ClobClient, ApiCreds

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

    print(f"  Starting stake: ${stake:.2f} pUSD\n")

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
                market = resolve_market(slug)
                if market: break
                time.sleep(1)
            if not market:
                print("  Market not found. Skipping.")
                time.sleep(max(10, w_e - time.time())); continue

            print(f"  Market: {market['title']}\n")

            target_wake = w_e - WAKE_UP_BEFORE
            sleep_time  = target_wake - time.time()
            if sleep_time > 0:
                print(f"  Sleeping {int(sleep_time)}s -> waking at T-{WAKE_UP_BEFORE}s ({fmt(target_wake)})...\n")
                time.sleep(sleep_time)

            side, entry_price, win = run_probe_phase(ws, ptb, w_e, market, client, stake)

            if win is True:
                payout = stake / entry_price if entry_price else stake
                stake  = round(payout, 2)
                print(f"  WIN! Rolled over -> next stake: ${stake:.2f} pUSD\n")
            elif win is False:
                stake = STARTING_STAKE_USD
                print(f"  LOSS. Resetting stake -> ${stake:.2f} pUSD\n")
            else:
                print(f"  No outcome. Stake unchanged -> ${stake:.2f} pUSD\n")

            time.sleep(max(1, w_e - time.time()))

        except Exception as e:
            print(f"\n  ERROR: {e}")
            traceback.print_exc()
            time.sleep(10)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Stopped by user.")
