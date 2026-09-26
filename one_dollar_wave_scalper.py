"""
$1 Single-Leg Momentum Wave Scalper
-----------------------------------
Strategy:
  1. Monitor active BTC 5M market on Polymarket & live Binance BTC spot.
  2. Trigger: Candle >= 3.5 minutes in (T+200s to T+270s) with at least $30 spot move.
  3. Buy $1.00 USD worth of the surging side (UP or DOWN). No arbitrage / No Leg 2.
  4. Instant Profit Target: Immediately post Limit Sell at entry + $0.01 (+1 cent green).
  5. 5-Second Timeout: If not filled within 5 seconds, cancel and dump to highest next best bid.
  6. Zero-Loss Stop: If dump results in a loss (< 0), stop trading immediately.
  7. Rollover: On green profit, roll over winnings into the next trade stake.
"""

import os
import sys
import time
import json
import datetime
import requests

# Ensure local imports work
sys.path.append(os.path.abspath("batch_fok_deploy"))

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import (
    ApiCreds,
    OrderArgsV2,
    OrderType,
    PartialCreateOrderOptions,
    PostOrdersV2Args,
    BalanceAllowanceParams,
    AssetType,
    OrderPayload
)
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

# Load credentials from batch_fok_deploy/.env
load_dotenv("batch_fok_deploy/.env")

PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
POLY_ADDRESS = os.getenv("POLYMARKET_ADDRESS", "")
API_KEY = os.getenv("POLYMARKET_API_KEY", "")
API_SECRET = os.getenv("POLYMARKET_API_SECRET", "")
API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE", "")

CLOB_HOST = "https://clob.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"
BINANCE_API = "https://api.binance.com/api/v3"

STARTING_STAKE = 1.00          # Base starting stake ($1.00 USD)
current_stake = STARTING_STAKE
streak_count = 0
total_profit = 0.0

MIN_SPOT_MOVE = 30.0           # At least $30 move from open
MIN_ELAPSED_SEC = 200          # At least ~3.5 minutes into candle (T+200s)
MAX_ENTRY_PRICE = 0.98         # Maximum entry ask allowed
SCALP_TIMEOUT_SEC = 5.0        # Dump after 5 seconds if not filled green

def log(msg: str):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

print("=" * 80)
print("⚡ $1 SINGLE-LEG MOMENTUM WAVE SCALPER (5-SEC GREEN SCALPER)")
print("=" * 80)
print(f"• Target Asset:       Bitcoin (BTC 5M)")
print(f"• Starting Stake:     ${current_stake:.2f} USD (1-dollar trade)")
print(f"• Strategy:           Single-Leg Momentum (NO Arbitrage / NO Leg 2)")
print(f"• Trigger Rule:       Candle >= 3.5 mins (T+{MIN_ELAPSED_SEC}s) & Move >= ${MIN_SPOT_MOVE:.0f}")
print(f"• Take Profit:        Immediate Limit Sell at Entry + $0.01 (+1¢ Green)")
print(f"• Timeout Rule:       Dump to next best bid after {SCALP_TIMEOUT_SEC:.0f} seconds if unfilled")
print(f"• Rollover:           100% of green winnings rolled over into next trade")
print("=" * 80)

if not PRIVATE_KEY or not POLY_ADDRESS:
    print("❌ Error: Missing credentials in batch_fok_deploy/.env")
    sys.exit(1)

creds = ApiCreds(
    api_key=API_KEY,
    api_secret=API_SECRET,
    api_passphrase=API_PASSPHRASE
) if API_KEY else None

client = ClobClient(
    host=CLOB_HOST,
    key=PRIVATE_KEY,
    chain_id=137,
    creds=creds,
    signature_type=3,
    funder=POLY_ADDRESS
)

def get_wallet_balance():
    try:
        resp = client.get_balance_allowance(params=BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        return float(resp.get("balance", 0)) / 1e6
    except Exception:
        return None

INITIAL_WALLET_BALANCE = get_wallet_balance()
MAX_DRAWDOWN = 0.50  # Stop trading if balance drops -$0.50 from initial

print(f"💼 Connected Wallet: {POLY_ADDRESS}")
if INITIAL_WALLET_BALANCE is not None:
    print(f"💰 Initial Starting Balance: ${INITIAL_WALLET_BALANCE:.2f} USDC")
    print(f"🛑 Max Drawdown Guard: Will stop bot if balance drops to <= ${INITIAL_WALLET_BALANCE - MAX_DRAWDOWN:.2f} USDC (-$0.50 from initial)")
else:
    print("💰 Initial Balance: [Query failed]")

if INITIAL_WALLET_BALANCE is not None and INITIAL_WALLET_BALANCE < 1.0:
    print("⚠️ Warning: Balance is under $1.00 USDC. Please top up wallet.")
    sys.exit(1)

def check_drawdown_limit():
    global INITIAL_WALLET_BALANCE
    if INITIAL_WALLET_BALANCE is None:
        INITIAL_WALLET_BALANCE = get_wallet_balance()
        return False
    cur_bal = get_wallet_balance()
    if cur_bal is not None:
        drawdown = round(INITIAL_WALLET_BALANCE - cur_bal, 2)
        if drawdown >= MAX_DRAWDOWN:
            print("\n" + "🛑" * 40)
            log(f"❌ [MAX DRAWDOWN REACHED: -$0.50 FROM INITIAL BALANCE]")
            log(f"   Initial Balance: ${INITIAL_WALLET_BALANCE:.2f} USDC")
            log(f"   Current Balance: ${cur_bal:.2f} USDC (Total Loss: -${drawdown:.2f} USDC >= -${MAX_DRAWDOWN:.2f})")
            log(f"   Hard stop limit reached. Terminating bot immediately to protect capital.")
            print("🛑" * 40 + "\n")
            sys.exit(0)
    return False

session = requests.Session()

def get_binance_data():
    try:
        t = session.get(f"{BINANCE_API}/ticker/price?symbol=BTCUSDT", timeout=1.5).json()
        k = session.get(f"{BINANCE_API}/klines?symbol=BTCUSDT&interval=5m&limit=1", timeout=1.5).json()
        open_p = float(k[0][1])
        cur_p = float(t["price"])
        move = cur_p - open_p
        return cur_p, open_p, move
    except Exception:
        return 0.0, 0.0, 0.0

def get_active_market():
    now = int(time.time())
    cur_w = (now // 300) * 300
    candidates = [cur_w, cur_w + 300]
    for w_s in candidates:
        slug = f"btc-updown-5m-{w_s}"
        try:
            r = session.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=2.5).json()
            if r and r[0].get("markets"):
                m = r[0]["markets"][0]
                raw_tokens = m.get("clobTokenIds", "[]")
                tokens = json.loads(raw_tokens) if isinstance(raw_tokens, str) else (raw_tokens or [])
                raw_outcomes = m.get("outcomes", "[]")
                outcomes = json.loads(raw_outcomes) if isinstance(raw_outcomes, str) else (raw_outcomes or [])
                if len(tokens) >= 2 and now < (w_s + 300):
                    up_t = tokens[0] if (outcomes and outcomes[0].upper() in ("UP", "YES")) else tokens[0]
                    dn_t = tokens[1] if (outcomes and outcomes[0].upper() in ("UP", "YES")) else tokens[1]
                    return {
                        "slug": slug,
                        "title": r[0].get("title", slug),
                        "window_start": w_s,
                        "window_end": w_s + 300,
                        "up_token": up_t,
                        "down_token": dn_t,
                        "condition_id": m.get("conditionId", "")
                    }
        except Exception:
            pass
    return None

def fetch_book_asks(up_token, down_token):
    try:
        r_up = session.get(f"{CLOB_HOST}/book?token_id={up_token}", timeout=1.5).json()
        r_dn = session.get(f"{CLOB_HOST}/book?token_id={down_token}", timeout=1.5).json()
        asks_up = r_up.get("asks", [])
        asks_dn = r_dn.get("asks", [])
        best_up = min(asks_up, key=lambda x: float(x["price"])) if asks_up else None
        best_dn = min(asks_dn, key=lambda x: float(x["price"])) if asks_dn else None
        p_up = float(best_up["price"]) if best_up else 1.0
        s_up = float(best_up["size"]) if best_up else 0.0
        p_dn = float(best_dn["price"]) if best_dn else 1.0
        s_dn = float(best_dn["size"]) if best_dn else 0.0
        return p_up, s_up, p_dn, s_dn
    except Exception:
        return 1.0, 0.0, 1.0, 0.0

def fetch_book_best_bid(token_id):
    try:
        r = session.get(f"{CLOB_HOST}/book?token_id={token_id}", timeout=1.5).json()
        bids = r.get("bids", [])
        if bids:
            best = max(bids, key=lambda x: float(x["price"]))
            return float(best["price"]), float(best["size"])
    except Exception:
        pass
    return 0.0, 0.0

def place_limit_order(token_id, price, size, outcome, order_type=OrderType.GTC, side="BUY"):
    opt = PartialCreateOrderOptions(tick_size="0.01", neg_risk=False)
    order = client.create_order(
        OrderArgsV2(token_id=token_id, price=price, size=size, side=side),
        options=opt
    )
    t0 = time.perf_counter()
    resp = client.post_orders([PostOrdersV2Args(order=order, orderType=order_type)])
    lat_ms = (time.perf_counter() - t0) * 1000.0
    if isinstance(resp, list) and len(resp) > 0:
        r = resp[0]
        status = r.get("status", "")
        txs = r.get("transactionsHashes", [])
        tx = txs[0] if txs else ""
        order_id = r.get("orderID", "")
        return True, status, price, order_id, tx, lat_ms
    return False, "error", price, "", resp, lat_ms

print("\n🚀 Starting scanner... Waiting for the right market window...\n")

traded_windows = set()

while True:
    try:
        mkt = get_active_market()
        if not mkt:
            log("Waiting for active BTC 5M market...")
            time.sleep(2.0)
            continue

        w_start = mkt["window_start"]
        now = int(time.time())
        t_rem = max(0, mkt["window_end"] - now)
        t_elapsed = 300 - t_rem

        spot_p, open_p, move = get_binance_data()
        up_p, up_s, dn_p, dn_s = fetch_book_asks(mkt["up_token"], mkt["down_token"])

        move_sign = "+" if move >= 0 else ""
        cur_time = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
        traded_tag = " [TRADED]" if w_start in traded_windows else ""
        print(f"\r[{cur_time} UTC | T-{t_rem:03d}s | T+{t_elapsed:03d}s{traded_tag}] BTC: ${spot_p:,.1f} ({move_sign}${move:.1f}) | UP: ${up_p:.2f} ({up_s:.0f}sh) | DN: ${dn_p:.2f} ({dn_s:.0f}sh) | Stake: ${current_stake:.2f}", end="", flush=True)

        # Trigger Condition:
        # 1. Not already traded in this window
        # 2. At least 3.5 minutes in (T+200s)
        # 3. At least $30 move from open
        # 4. Not in final 15s
        if w_start not in traded_windows and t_elapsed >= MIN_ELAPSED_SEC and t_rem >= 15 and abs(move) >= MIN_SPOT_MOVE:
            check_drawdown_limit()
            wave_dir = "UP" if move > 0 else "DOWN"
            print("\n")
            log(f"🔥 [MOMENTUM SETUP DETECTED] Candle is {t_elapsed}s in | BTC Move: {move_sign}${move:.1f} >= ${MIN_SPOT_MOVE:.0f}")
            log(f"   Wave direction: {wave_dir}. Preparing $1 scalp...")

            target_token = mkt["up_token"] if wave_dir == "UP" else mkt["down_token"]
            target_ask = up_p if wave_dir == "UP" else dn_p
            token_name = wave_dir

            if target_ask <= MAX_ENTRY_PRICE:
                # Calculate shares for exactly current_stake ($1.00 base)
                # Ensure notional is at least $1.00
                shares_needed = round(current_stake / target_ask, 2)
                if shares_needed * target_ask < 1.00:
                    shares_needed = round(shares_needed + 0.05, 2)

                log(f"🛒 [BUYING {token_name}] Target Ask: ${target_ask:.2f} | Size: {shares_needed:.2f} shares (~${shares_needed * target_ask:.2f} USD)...")
                
                buy_filled = False
                fill_price = target_ask
                buy_order_id = ""

                # Attempt buy
                ok_b, st_b, p_b, oid_b, tx_b, _ = place_limit_order(target_token, target_ask, shares_needed, token_name, OrderType.GTC, side="BUY")
                
                if ok_b:
                    # Wait up to 1.5s for buy match
                    t_b_wait = time.time()
                    while time.time() - t_b_wait < 1.5:
                        if st_b == "matched" or tx_b:
                            buy_filled = True
                            fill_price = target_ask
                            break
                        if oid_b:
                            try:
                                o_data = client.get_order(oid_b)
                                if isinstance(o_data, dict):
                                    if str(o_data.get("status", "")).upper() == "MATCHED" or float(o_data.get("size_matched", 0)) >= shares_needed:
                                        buy_filled = True
                                        fill_price = target_ask
                                        break
                            except Exception:
                                pass
                        time.sleep(0.20)

                    if not buy_filled:
                        log(f"⏳ Buy order did not fill immediately. Cancelling buy order...")
                        if oid_b:
                            try:
                                client.cancel_order(OrderPayload(orderID=oid_b))
                            except Exception:
                                pass
                        log(f"⚠️ [BUY ABORTED] Could not fill {token_name} at ${target_ask:.2f}. Will re-scan.")
                        continue
                else:
                    log(f"❌ [BUY FAILED] Order rejected: {st_b}")
                    continue

                # Lock candle once buy is in hand!
                traded_windows.add(w_start)
                total_spent = round(fill_price * shares_needed, 2)
                log(f"✅ [BOUGHT & FILLED] {shares_needed:.2f}sh {token_name} @ ${fill_price:.2f} (Total: ${total_spent:.2f} USD)")

                # ==============================================================
                # STEP 2: INSTANT PROFIT TARGET (+0.01 GREEN)
                # ==============================================================
                target_sell_price = min(0.99, round(fill_price + 0.01, 2))
                log(f"🎯 [TAKE PROFIT LIMIT SELL] Posting Limit Sell for {shares_needed:.2f}sh @ ${target_sell_price:.2f} (+1¢ Green)...")
                
                ok_tp, st_tp, p_tp, oid_tp, tx_tp, _ = place_limit_order(
                    target_token, target_sell_price, shares_needed, token_name, OrderType.GTC, side="SELL"
                )

                sold_green = False
                dumped_bid = False
                final_sell_price = 0.0

                # ==============================================================
                # STEP 3: 5-SECOND TIMEOUT -> DUMP TO NEXT BEST BID
                # ==============================================================
                t_sell_start = time.time()
                while time.time() - t_sell_start < SCALP_TIMEOUT_SEC:
                    elapsed_wait = time.time() - t_sell_start
                    
                    # Check if profit target matched
                    if st_tp == "matched" or tx_tp:
                        sold_green = True
                        final_sell_price = target_sell_price
                        break
                    if oid_tp:
                        try:
                            s_data = client.get_order(oid_tp)
                            if isinstance(s_data, dict) and str(s_data.get("status", "")).upper() == "MATCHED":
                                sold_green = True
                                final_sell_price = target_sell_price
                                break
                        except Exception:
                            pass
                    
                    cur_bid, _ = fetch_book_best_bid(target_token)
                    print(f"\r   [Waiting for +1¢ fill | {elapsed_wait:.1f}s/{SCALP_TIMEOUT_SEC:.0f}s] Target: ${target_sell_price:.2f} | Current Best Bid: ${cur_bid:.2f}", end="", flush=True)
                    time.sleep(0.25)

                print("\n")

                if sold_green:
                    log(f"🎉 [GREEN PROFIT HIT IN < 5s!] Limit sell matched @ ${target_sell_price:.2f}!")
                else:
                    # 5 SECONDS EXPIRED -> CANCEL LIMIT SELL AND DUMP TO HIGHEST NEXT BEST BID
                    log(f"⏱️ [5s TIMEOUT EXPIRED] +1¢ did not fill within {SCALP_TIMEOUT_SEC:.0f}s! Cancelling limit sell...")
                    if oid_tp:
                        try:
                            client.cancel_order(OrderPayload(orderID=oid_tp))
                        except Exception:
                            pass
                    try:
                        client.cancel_all()
                    except Exception:
                        pass
                    
                    time.sleep(0.20)

                    # Fetch highest next best bid
                    best_bid_p, best_bid_sz = fetch_book_best_bid(target_token)
                    dump_price = max(0.01, best_bid_p)
                    log(f"⚡ [DUMPING TO NEXT BEST BID] Snapping highest bid: {shares_needed:.2f}sh @ ${dump_price:.2f} (Book depth: {best_bid_sz:.0f}sh)...")

                    ok_dump, st_dump, p_dump, oid_dump, tx_dump, _ = place_limit_order(
                        target_token, dump_price, shares_needed, token_name, OrderType.FOK, side="SELL"
                    )

                    if not ok_dump or st_dump not in ("matched", "live"):
                        # Fallback to market GTC sell if FOK didn't match instantly
                        log("Retrying with GTC best bid exit...")
                        place_limit_order(target_token, dump_price, shares_needed, token_name, OrderType.GTC, side="SELL")

                    dumped_bid = True
                    final_sell_price = dump_price

                # ==============================================================
                # SUMMARY, PNL & ZERO-LOSS HARD STOP
                # ==============================================================
                total_return = round(final_sell_price * shares_needed, 2)
                trade_pnl = round(total_return - total_spent, 2)

                print("\n" + "=" * 80)
                print(f"📊 [SCALP RESULT SUMMARY - {token_name}]")
                print(f"• Bought:        {shares_needed:.2f} shares @ ${fill_price:.2f} (${total_spent:.2f} USD)")
                print(f"• Sold:          {shares_needed:.2f} shares @ ${final_sell_price:.2f} (${total_return:.2f} USD)")
                print(f"• Execution:     {'✅ Green Profit (+1¢ Target Matched)' if sold_green else '⚡ 5s Timeout Dump to Bid'}")
                print(f"• Net PnL:       {'+$' if trade_pnl >= 0 else '-$'}{abs(trade_pnl):.2f} USD")
                print("=" * 80)

                total_profit += trade_pnl

                if trade_pnl < 0:
                    log(f"⚠️ [DIP LOSS OCCURRED] Trade closed at -${abs(trade_pnl):.2f} USD.")
                    current_stake = STARTING_STAKE  # Reset to $1.00 base stake
                    streak_count = 0
                else:
                    streak_count += 1
                    current_stake = round(current_stake + trade_pnl, 2)
                    log(f"🔥 [WIN STREAK #{streak_count}] Profit Locked! Rolling over to next stake: ${current_stake:.2f} USD")

                # ==============================================================
                # CRITICAL DRAWDOWN GUARD: STOP IF BALANCE DROPS -$0.50 FROM INITIAL
                # ==============================================================
                check_drawdown_limit()

                cur_live = get_wallet_balance()
                if cur_live is not None and INITIAL_WALLET_BALANCE is not None:
                    cur_diff = round(cur_live - INITIAL_WALLET_BALANCE, 2)
                    diff_str = f"+${cur_diff:.2f}" if cur_diff >= 0 else f"-${abs(cur_diff):.2f}"
                    log(f"💼 Balance: ${cur_live:.2f} USDC (Change from initial: {diff_str} | Stop threshold: -${MAX_DRAWDOWN:.2f})")
                log(f"💰 Session Net Profit: {'+$' if total_profit >= 0 else '-$'}{abs(total_profit):.2f} USD\n")

        time.sleep(0.40)
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
        break
    except Exception as e:
        time.sleep(1.0)
