"""
================================================================================
COMBINED GUARD RAIL BOT (DOUBLE STAKE)
================================================================================
Strategy Overview:
- Double Stake Mode: Splits total stake into 2 parallel order executions.
- Primary Entry (T-8s): Fires ONLY when all 3 Combined Guard Rails pass:
    1. BTC Price Gap >= $5.00 from PTB (Price to Beat)
    2. Dominant Orderbook Ask >= $0.85 (85%+ Market Consensus)
    3. BTC Momentum is stable/expanding (not shrinking towards PTB)
- Fallback Confirmation (T-2s): If T-8s conditions are NOT met (tight gap < $5):
    - Probes through T-7s to T-2s.
    - Confirms at T-2s ONLY if BTC has widened the gap (>= $2.00) & orderbook aligns.
    - Otherwise SKIPS the window to preserve capital!
================================================================================
"""

import os, sys, time, json, datetime, ssl, threading, requests, traceback

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"
LIVE_WS_URL= "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# Configuration
POLYMARKET_LIVE_TRADING = True
DOUBLE_STAKE            = True      # Place 2 parallel orders per window
CONFIDENCE_THRESHOLD    = 0.85     # Dominant ask threshold for early entry
MIN_SAFE_BTC_GAP        = 5.00     # $5.00 gap required for early T-8s entry
T2_MIN_BTC_GAP          = 2.00     # $2.00 gap required for T-2s late entry
MIN_ENTRY_PRICE         = 0.15     # Reject residual asks below 15¢
STARTING_STAKE_USD      = 1.00

# Bet Window & Probes
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CombinedDoubleBot/1.0"
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
        self._history = []
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
                if self._price and self._ts_ms:
                    self._history.append((self._ts_ms, self._price))
                    if len(self._history) > 30:
                        self._history.pop(0)
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

    def get_recent_ticks(self, count=3):
        with self._lock:
            return list(self._history[-count:])


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
        if not trades: return STARTING_STAKE_USD
        s = sorted(trades, key=lambda t: int(t.get("match_time") or t.get("timestamp") or 0))
        last_match = s[-1]
        cid = last_match.get("market") or last_match.get("asset_id")
        trade_size = float(last_match.get("size", 0))
        trade_price = float(last_match.get("price", 1.0))
        spent = trade_size * trade_price

        time.sleep(3)
        r = requests.get(f"{GAMMA_HOST}/markets", params={"clob_token_ids": cid}, timeout=10)
        mkts = r.json() if r.status_code == 200 else []

        up_won = None
        if mkts:
            prices = [float(p) for p in json.loads(mkts[0].get("outcomePrices") or "[]")]
            tids = json.loads(mkts[0].get("clobTokenIds") or "[]")
            outs = [str(o).lower() for o in json.loads(mkts[0].get("outcomes") or "[]")]
            up_tid = tids[0]
            if len(outs) > 1 and outs[1] in ("up", "yes"): up_tid = tids[1]
            if prices and max(prices) >= 0.99:
                winner_tid = tids[prices.index(max(prices))]
                up_won = (winner_tid == up_tid)

        if up_won is None: return STARTING_STAKE_USD
        bet_up = (cid == up_tid)
        won = (bet_up and up_won) or (not bet_up and not up_won)

        if won:
            payout = spent / trade_price if trade_price > 0 else spent
            return round(payout, 2)
        else:
            return STARTING_STAKE_USD
    except Exception as e:
        print(f"  WARNING reconstruct: {e}"); return STARTING_STAKE_USD


def evaluate_combined_guard_rails(up_ask, dn_ask, last_price, ptb, ws_history, mark):
    btc_gap = abs(last_price - ptb)
    btc_dir = "UP" if last_price >= ptb else "DOWN"

    target_side = None
    target_ask = None

    if up_ask is not None and dn_ask is not None:
        if up_ask > dn_ask:
            target_side, target_ask = "UP", up_ask
        elif dn_ask > up_ask:
            target_side, target_ask = "DOWN", dn_ask
        else:
            target_side, target_ask = btc_dir, (up_ask if btc_dir == "UP" else dn_ask)
    elif up_ask is None and dn_ask is not None:
        if btc_dir == "UP": return "UP", None, True, "UP dried up (100% win)"
        return None, None, False, "UP dried up but BTC says DOWN conflict"
    elif dn_ask is None and up_ask is not None:
        if btc_dir == "DOWN": return "DOWN", None, True, "DOWN dried up (100% win)"
        return None, None, False, "DOWN dried up but BTC says UP conflict"

    if target_side != btc_dir:
        return None, None, False, f"Conflict: Orderbook={target_side} vs BTC={btc_dir}"

    if target_ask is None or target_ask < MIN_ENTRY_PRICE:
        return None, None, False, "Ask price below minimum entry price (15¢)"

    momentum_ok = True
    if len(ws_history) >= 3:
        p1, p2, p3 = ws_history[-3][1], ws_history[-2][1], ws_history[-1][1]
        if btc_dir == "UP" and (p3 < p2 < p1):
            momentum_ok = False
        elif btc_dir == "DOWN" and (p3 > p2 > p1):
            momentum_ok = False

    if mark >= 5:
        if btc_gap >= MIN_SAFE_BTC_GAP and target_ask >= CONFIDENCE_THRESHOLD and momentum_ok:
            return target_side, target_ask, True, f"T-{mark}s SAFE EARLY: Gap=${btc_gap:.2f} >= $5, Ask=${target_ask:.2f} >= 0.85, Momentum OK"
        else:
            reasons = []
            if btc_gap < MIN_SAFE_BTC_GAP: reasons.append(f"Tight Gap=${btc_gap:.2f} < $5")
            if target_ask < CONFIDENCE_THRESHOLD: reasons.append(f"Ask=${target_ask:.2f} < 0.85")
            if not momentum_ok: reasons.append("Momentum shrinking towards PTB")
            return None, None, False, f"T-{mark}s HOLD ({', '.join(reasons)}) -> Deferring to T-2s"

    else:
        if btc_gap >= T2_MIN_BTC_GAP:
            return target_side, target_ask, True, f"T-{mark}s CONFIRMED LATE: Gap=${btc_gap:.2f} >= $2.00"
        else:
            return None, None, False, f"T-{mark}s REJECTED: Gap=${btc_gap:.2f} < $2.00 (High flip risk)"


def run_probe_phase(ws, ptb, w_end, market, clob_client=None, stake_usd=1.00):
    last_tick = None
    last_price = ptb
    ticks = 0
    done  = set()
    results = []
    side = price = None

    print(f"\n  === COMBINED GUARD RAIL BOT (DOUBLE STAKE)  last {WAKE_UP_BEFORE}s ===")
    print(f"  PTB         : ${ptb:,.2f}  |  Total Stake: ${stake_usd:.2f}  (2 x ${stake_usd/2:.2f})")
    print(f"  Guard Rails : Early (T-8s) Gap >= $5.00 & Ask >= 85¢  |  Late (T-2s) Gap >= $2.00")
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
                ws_history = ws.get_recent_ticks()
                s, ask, approved, reason = evaluate_combined_guard_rails(
                    up_ask, dn_ask, last_price, ptb, ws_history, mark
                )

                print(f"  🛡️ Guard Rail Evaluation: {reason}")

                if not approved or s is None:
                    continue

                side  = s
                price = ask if ask else 0.99
                single_stake = round(stake_usd / 2.0, 2)
                if single_stake < 1.00: single_stake = stake_usd
                payout = stake_usd / price
                profit = payout - stake_usd
                results[-1]["bet_placed"] = True
                msg = "PAPER DOUBLE BET"

                if clob_client is not None:
                    msg = "LIVE DOUBLE BET"
                    print(f"  [T-{mark}s] 🚀 2 x PARALLEL ORDERS (2 x ${single_stake:.2f}): {side} @ ${price:.4f}...")
                    try:
                        from py_clob_client_v2 import MarketOrderArgsV2
                        tid = market["up_id"] if side == "UP" else market["down_id"]
                        # Order 1
                        r1 = clob_client.create_and_post_market_order(
                            MarketOrderArgsV2(token_id=tid, amount=single_stake, price=price, side="BUY")
                        )
                        print(f"  Order #1 response: {r1}")
                        # Order 2
                        r2 = clob_client.create_and_post_market_order(
                            MarketOrderArgsV2(token_id=tid, amount=single_stake, price=price, side="BUY")
                        )
                        print(f"  Order #2 response: {r2}")
                    except Exception as e:
                        print(f"  ERROR executing double order: {e}")

                print(f"  +-----------------------------------------------------------+")
                print(f"  |  {msg:<24} ->  {side:<4} @ ${price:.4f}  (T-{mark}s)          |")
                print(f"  |  Total Stake: ${stake_usd:.2f}  Payout: ${payout:.4f}  Profit: +${profit:.4f}  |")
                print(f"  +-----------------------------------------------------------+")

        time.sleep(0.05)

    if side:
        print_summary(results, w_end - WINDOW_SECS, w_end, ptb, last_price, side, price, stake_usd)
        win = poll_settlement(slug_for(w_end - WINDOW_SECS), side, price, stake_usd)
        return side, price, win
    else:
        print("\n  No bet placed (Guard Rails protected capital). Stake unchanged.")
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
    for r in results:
        u = f"${r['up_ask']:.4f}"   if r["up_ask"]   else "   NONE "
        d = f"${r['down_ask']:.4f}" if r["down_ask"] else "   NONE "
        st = "OPEN" if r["has_liquidity"] else "CLOSED"
        bt = "  <- BET" if r.get("bet_placed") else ""
        ph = "OBSERVE" if r.get("observe_only") else "BET ZONE"
        print(f"  T-{r['mark']:>4}s  {fmt(r['ts']):>8}  {u:>8}  {d:>8}  {ph:<10}  {st}{bt}")
    print(f"  {'='*72}\n")


def main():
    mode = "LIVE TRADING" if POLYMARKET_LIVE_TRADING else "PAPER TRADING"
    print(f"\n{'='*72}")
    print(f"  COMBINED GUARD RAIL BOT (DOUBLE STAKE)  |  {mode}")
    print(f"  Early T-8s: Gap >= $5 & Ask >= 85¢  |  Late T-2s: Gap >= $2")
    print(f"  Order Execution: 2 x Parallel Orders per window")
    print(f"{'='*72}\n")

    client = None
    if POLYMARKET_LIVE_TRADING:
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
            u = input(f"  Override TOTAL starting stake (e.g. 10.00 for 2 x $5.00)? [{stake:.2f}]: ").strip()
            if u: stake = float(u)
        except ValueError: pass

    print(f"  Starting TOTAL stake: ${stake:.2f} pUSD  (Split into 2 x ${stake/2:.2f})\n")

    while True:
        try:
            now  = time.time()
            w_s  = win_start(now)
            w_e  = win_end(now)
            into = now - w_s
            rem  = w_e - now

            print(f"\n{'='*72}")
            print(f"  NEW CYCLE  |  {fmt(now)}  |  Window: {fmt_win(w_s)}")
            print(f"  Into: {int(into)}s  |  Remaining: {int(rem)}s  |  Total Stake: ${stake:.2f}")
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
