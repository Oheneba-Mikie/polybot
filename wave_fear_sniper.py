"""
Single-Trade Local Panic Wave Sniper (Real Money - 5 Shares)
-------------------------------------------------------------
Strategy:
  1. Watch active BTC 5M market on Polymarket & live Binance BTC spot.
  2. Wait until candle is ~3.5 minutes in (T+200s to T+270s) with at least $30 spot move.
  3. Step 1: Buy 5 shares of the surging panic side at market ask (typically $0.80 - $0.88).
  4. Step 2: Sit and wait for the losing side to get cheap (<= $0.08).
  5. Step 3: Snap 5 shares of the cheap side -> Arbitrage 100% sealed!
  6. Prints full trade summary and exits after this single trade.
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
    AssetType
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

ORDER_SIZE = 5.0                # 5 shares
MIN_SPOT_MOVE = 30.0            # At least $30 move from open
MIN_ELAPSED_SEC = 200           # At least ~3.5 minutes into candle (T+200s)
MAX_LEG1_PRICE = 0.89           # Buy panic surging side at <= $0.89
CHEAP_TARGET_PRICE = 0.08       # Sit and wait for cheap side <= $0.08 (8c)

def log(msg: str):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

print("=" * 80)
print("⚡ POLYMARKET 5-SHARE REAL MONEY PANIC WAVE SNIPER (1 TRADE ONLY)")
print("=" * 80)
print(f"• Target Asset:      Bitcoin (BTC 5M)")
print(f"• Order Size:        {ORDER_SIZE} shares")
print(f"• Trigger Rule:      Candle >= 3.5 mins (T+{MIN_ELAPSED_SEC}s) & Move >= ${MIN_SPOT_MOVE:.0f}")
print(f"• Leg 1 Entry:       Surging panic side <= ${MAX_LEG1_PRICE:.2f}")
print(f"• Leg 2 Target:      Sit & wait for opposite side <= ${CHEAP_TARGET_PRICE:.2f}")
print("=" * 80)

# 1. Initialize CLOB Client
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

# 2. Check Live Wallet Balance
try:
    resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=3))
    raw_bal = float(resp.get("balance", 0)) / 1e6
    print(f"💼 Connected Wallet: {POLY_ADDRESS}")
    print(f"💰 Live USDC Balance: ${raw_bal:.2f} USDC")
    if raw_bal < 5.0:
        print("⚠️ Warning: Balance is under $5.00 USDC. Might not be enough for 5 shares.")
except Exception as e:
    print(f"⚠️ Balance check error: {e}")

session = requests.Session()

def get_binance_data():
    try:
        # Get 5m candle open
        k = session.get(f"{BINANCE_API}/klines?symbol=BTCUSDT&interval=5m&limit=1", timeout=2).json()
        open_p = float(k[0][1])
        # Get live ticker
        t = session.get(f"{BINANCE_API}/ticker/price?symbol=BTCUSDT", timeout=1.5).json()
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
                tokens = json.loads(m.get("clobTokenIds", "[]")) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds", [])
                outcomes = json.loads(m.get("outcomes", "[]")) if isinstance(m.get("outcomes"), str) else m.get("outcomes", [])
                if len(tokens) >= 2 and now < (w_s + 300):
                    up_t = tokens[0] if (outcomes and outcomes[0].upper() in ("UP", "YES")) else tokens[0]
                    dn_t = tokens[1] if (outcomes and outcomes[0].upper() in ("UP", "YES")) else tokens[1]
                    return {
                        "slug": slug,
                        "title": r[0].get("title", slug),
                        "window_start": w_s,
                        "window_end": w_s + 300,
                        "up_token": up_t,
                        "down_token": dn_t
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

def place_limit_order(token_id, price, size, outcome, order_type=OrderType.GTC):
    opt = PartialCreateOrderOptions(tick_size="0.01", neg_risk=False)
    order = client.create_order(
        OrderArgsV2(token_id=token_id, price=price, size=size, side="BUY"),
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

while True:
    try:
        mkt = get_active_market()
        if not mkt:
            log("Waiting for active BTC 5M market...")
            time.sleep(2.0)
            continue

        now = int(time.time())
        t_rem = max(0, mkt["window_end"] - now)
        t_elapsed = 300 - t_rem

        spot_p, open_p, move = get_binance_data()
        up_p, up_s, dn_p, dn_s = fetch_book_asks(mkt["up_token"], mkt["down_token"])

        # Display progress line
        move_sign = "+" if move >= 0 else ""
        print(f"\r[T-{t_rem:03d}s | T+{t_elapsed:03d}s] BTC: ${spot_p:,.1f} ({move_sign}${move:.1f}) | UP: ${up_p:.2f} ({up_s:.0f}sh) | DN: ${dn_p:.2f} ({dn_s:.0f}sh)", end="", flush=True)

        # Condition Check:
        # 1. At least 3.5 minutes in (T+200s)
        # 2. At least $30 move from open
        # 3. Not in final 15s
        if t_elapsed >= MIN_ELAPSED_SEC and t_rem >= 15 and abs(move) >= MIN_SPOT_MOVE:
            wave_dir = "UP" if move > 0 else "DOWN"
            print("\n")
            log(f"🔥 [SETUP DETECTED] Candle is {t_elapsed}s in (3.5+ min) | BTC Move: {move_sign}${move:.1f} >= ${MIN_SPOT_MOVE:.0f}")
            log(f"   People are panic buying {wave_dir}! Evaluating order book...")

            if wave_dir == "UP":
                leg1_token, leg1_ask, leg1_name = mkt["up_token"], up_p, "UP"
                leg2_token, leg2_name = mkt["down_token"], "DOWN"
            else:
                leg1_token, leg1_ask, leg1_name = mkt["down_token"], dn_p, "DOWN"
                leg2_token, leg2_name = mkt["up_token"], "UP"

            if leg1_ask <= MAX_LEG1_PRICE:
                log(f"🚀 [STEP 1: BUYING PANIC SIDE] Placing Limit Order (GTC) for {ORDER_SIZE}sh {leg1_name} @ ${leg1_ask:.2f}...")
                ok1, st1, fill_p1, oid1, tx1, lat1 = place_limit_order(leg1_token, leg1_ask, ORDER_SIZE, leg1_name, OrderType.GTC)

                if ok1 and (st1 == "matched" or tx1):
                    log(f"✅ [LEG 1 FILLED in {lat1:.1f}ms] Bought {ORDER_SIZE}sh {leg1_name} @ ${fill_p1:.2f}! (Tx: {tx1[:10]}...)")
                    
                    # Step 2: Place resting limit bid for 5 shares at cheap target price directly on the book
                    log(f"📝 [STEP 2: POSTING RESTING BID] Placing Limit Bid (GTC) for {ORDER_SIZE}sh {leg2_name} @ ${CHEAP_TARGET_PRICE:.2f} on book...")
                    ok2, st2, bid_p2, oid2, tx2, lat2 = place_limit_order(leg2_token, CHEAP_TARGET_PRICE, ORDER_SIZE, leg2_name, OrderType.GTC)
                    
                    leg2_filled = False
                    leg2_price = CHEAP_TARGET_PRICE

                    if ok2 and st2 == "matched":
                        leg2_filled = True
                        leg2_price = bid_p2
                        log(f"⚡ [LEG 2 INSTANT MATCH] 5sh {leg2_name} filled immediately @ ${bid_p2:.2f}!")
                    elif ok2 and st2 == "live":
                        log(f"⏳ [RESTING BID ACTIVE] 5sh {leg2_name} bid resting @ ${CHEAP_TARGET_PRICE:.2f} (Order ID: {oid2[:12]}...). Sitting & waiting...")

                    # Sit and wait loop
                    while not leg2_filled:
                        now_loop = int(time.time())
                        rem_loop = max(0, mkt["window_end"] - now_loop)

                        # Check if resting order got filled
                        if oid2:
                            try:
                                o_data = client.get_order(oid2)
                                if isinstance(o_data, dict):
                                    o_status = str(o_data.get("status", "")).upper()
                                    matched_sz = float(o_data.get("size_matched", 0))
                                    if o_status == "MATCHED" or matched_sz >= ORDER_SIZE:
                                        leg2_filled = True
                                        leg2_price = CHEAP_TARGET_PRICE
                                        print("\n")
                                        log(f"🎉 [RESTING BID FILLED!] 5sh {leg2_name} matched on the book @ ${CHEAP_TARGET_PRICE:.2f}!")
                                        break
                            except Exception:
                                pass

                        _up_p, _, _dn_p, _ = fetch_book_asks(mkt["up_token"], mkt["down_token"])
                        cur_cheap_p = _dn_p if leg2_name == "DOWN" else _up_p

                        print(f"\r   [Waiting for fill | T-{rem_loop:02d}s] {leg2_name} Ask: ${cur_cheap_p:.2f} (Resting Bid: ${CHEAP_TARGET_PRICE:.2f})", end="", flush=True)

                        # If market ask drops directly to target and resting bid didn't trigger, take it
                        if cur_cheap_p <= CHEAP_TARGET_PRICE:
                            print("\n")
                            log(f"⚡ [CHEAP ASK HIT] {leg2_name} ask is ${cur_cheap_p:.2f} <= ${CHEAP_TARGET_PRICE:.2f}! Snapping 5sh...")
                            ok_snap, st_snap, p_snap, _, tx_snap, _ = place_limit_order(leg2_token, cur_cheap_p, ORDER_SIZE, leg2_name, OrderType.GTC)
                            if ok_snap and (st_snap == "matched" or tx_snap):
                                leg2_filled = True
                                leg2_price = p_snap
                                break

                        # Safeguard at T-10s
                        if rem_loop <= 10:
                            print("\n")
                            try:
                                client.cancel_all()
                            except Exception:
                                pass
                            log(f"ℹ️ 10s remaining in candle. Cancelled resting orders. Holding position.")
                            break

                        time.sleep(0.30)

                    # Final Summary
                    print("\n" + "=" * 80)
                    if leg2_filled:
                        total_cost_per_share = round(fill_p1 + leg2_price, 3)
                        total_spent = round(total_cost_per_share * ORDER_SIZE, 2)
                        payout = round(1.00 * ORDER_SIZE, 2)
                        profit = round(payout - total_spent, 2)
                        pct = round((profit / total_spent) * 100, 1)

                        print("🎉 [ARBITRAGE SEALED & 100% GUARANTEED PROFIT]")
                        print(f"• Leg 1 ({leg1_name}):   {ORDER_SIZE} shares @ ${fill_p1:.2f}")
                        print(f"• Leg 2 ({leg2_name}): {ORDER_SIZE} shares @ ${leg2_price:.2f}")
                        print(f"• Total Paid:       ${total_spent:.2f} (${total_cost_per_share:.3f} per pair)")
                        print(f"• Guaranteed Pay:   ${payout:.2f} USDC (at resolution)")
                        print(f"• Net Profit:       +${profit:.2f} USDC (+{pct}%)")
                        print("=" * 80)
                    else:
                        print(f"ℹ️ Trade finished: Leg 1 holding {ORDER_SIZE}sh {leg1_name} @ ${fill_p1:.2f}.")
                        print("=" * 80)

                    print("\n✅ Single-trade run complete. Exiting.\n")
                    sys.exit(0)
                else:
                    log(f"ℹ️ Leg 1 order not filled: {res1}. Continuing scan...")
            else:
                pass

        time.sleep(0.40)
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
        break
    except Exception as e:
        time.sleep(1.0)
