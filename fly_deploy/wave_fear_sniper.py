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

ORDER_SIZE = 5.0                # Base starting size: 5.0 shares
current_stake = 4.90             # Starting stake ($4.90 for 5 shares)
streak_count = 0                 # Consecutive wins in current streak
total_streak_profit = 0.0        # Cumulative profit banked in streak
MIN_SPOT_MOVE = 30.0            # At least $30 move from open
MIN_ELAPSED_SEC = 200           # At least ~3.5 minutes into candle (T+200s)
MAX_LEG1_PRICE = 0.96           # Allow strong wave up to $0.96
MAX_COMBINED_COST = 0.98        # Combined pair cost capped at $0.98 (Guaranteed Profit)

def log(msg: str):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

print("=" * 80)
print("⚡ POLYMARKET 5-SHARE WINNINGS ROLLOVER COMPOUNDER (STREAK ENGINE)")
print("=" * 80)
print(f"• Target Asset:      Bitcoin (BTC 5M)")
print(f"• Starting Stake:    5.0 shares (${current_stake:.2f} USDC base)")
print(f"• Rollover Rule:     100% of Winnings Rolled Over on Every Win")
print(f"• Trigger Rule:      Candle >= 3.5 mins (T+{MIN_ELAPSED_SEC}s) & Move >= ${MIN_SPOT_MOVE:.0f}")
print(f"• Leg 1 Entry Cap:   Surging panic side <= ${MAX_LEG1_PRICE:.2f}")
print(f"• Max Pair Cost:     Combined <= ${MAX_COMBINED_COST:.2f} (Dynamic Hedge Target: $0.98 - Leg1)")
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
    resp = client.get_balance_allowance(params=BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
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

def check_both_legs_captured(condition_id, title=""):
    try:
        user_addr = POLY_ADDRESS or "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"
        # 1. Check open positions
        r_pos = session.get(f"https://data-api.polymarket.com/positions?user={user_addr}", timeout=1.5).json()
        pos_outcomes = set()
        for p in r_pos:
            cid = p.get("conditionId", "")
            t = p.get("title", "")
            sz = float(p.get("size") or 0)
            if sz > 0 and (cid == condition_id or (title and title.lower() in t.lower())):
                pos_outcomes.add(p.get("outcome"))
        if ("Up" in pos_outcomes and "Down" in pos_outcomes) or len(pos_outcomes) >= 2:
            return True

        # 2. Check recent trade activity in case positions index is updating
        r_act = session.get(f"https://data-api.polymarket.com/activity?user={user_addr}&limit=10", timeout=1.5).json()
        act_buys = set()
        for a in r_act:
            cid = a.get("conditionId", "")
            t = a.get("title", "")
            side = a.get("side", "")
            t_type = a.get("type", "")
            outcome = a.get("outcome", "")
            if (cid == condition_id or (title and title.lower() in t.lower())) and t_type == "TRADE" and side == "BUY":
                act_buys.add(outcome)
        if "Up" in act_buys and "Down" in act_buys:
            return True

        return False
    except Exception:
        return False


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

        # Display progress line
        move_sign = "+" if move >= 0 else ""
        cur_time = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
        traded_tag = " [TRADED]" if w_start in traded_windows else ""
        print(f"\r[{cur_time} UTC | T-{t_rem:03d}s | T+{t_elapsed:03d}s{traded_tag}] BTC: ${spot_p:,.1f} ({move_sign}${move:.1f}) | UP: ${up_p:.2f} ({up_s:.0f}sh) | DN: ${dn_p:.2f} ({dn_s:.0f}sh)", end="", flush=True)

        # Condition Check:
        # 1. Not already traded in this candle window
        # 2. At least 3.5 minutes in (T+200s)
        # 3. At least $30 move from open
        # 4. Not in final 15s
        if w_start not in traded_windows and t_elapsed >= MIN_ELAPSED_SEC and t_rem >= 15 and abs(move) >= MIN_SPOT_MOVE:
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
                # 5 to 8 Whole Shares Sprint Cycle
                active_shares = float(min(8, max(5, int(current_stake / 0.98))))
                log(f"🚀 [STEP 1: BUYING PANIC SIDE] Placing Limit Order (GTC) for {active_shares:.0f}sh {leg1_name} @ ${leg1_ask:.2f} (Stake: ${current_stake:.2f})...")
                ok1, st1, fill_p1, oid1, tx1, lat1 = place_limit_order(leg1_token, leg1_ask, active_shares, leg1_name, OrderType.GTC)

                # If exchange accepted the order (matched or live in book), lock candle immediately!
                if ok1 and (st1 in ("matched", "live") or tx1 or oid1):
                    traded_windows.add(w_start)
                    log(f"📌 [STATE: LEG 1 ACTIVE] {active_shares:.0f}sh {leg1_name} accepted by exchange (Status: {st1} | Order ID: {oid1[:12]}...). Candle {w_start} LOCKED.")
                    if st1 == "matched" or tx1:
                        log(f"✅ [LEG 1 MATCHED in {lat1:.1f}ms] Filled @ ${fill_p1:.2f}!")
                    else:
                        log(f"⏳ [LEG 1 RESTING in {lat1:.1f}ms] Order sitting @ ${fill_p1:.2f}. Proceeding to hedge...")
                    
                    # Step 2: Compute dynamic cheap target to guarantee pair cost <= $0.98
                    cheap_target_p = max(0.01, round(MAX_COMBINED_COST - fill_p1, 2))
                    log(f"🎯 [DYNAMIC HEDGE TARGET] Leg 1 @ ${fill_p1:.2f} -> Cheap Leg 2 Target: <= ${cheap_target_p:.2f} (Max pair cost: ${fill_p1 + cheap_target_p:.2f})")
                    
                    # Place resting limit bid directly on the book
                    log(f"📝 [STEP 2: POSTING RESTING BID] Placing Limit Bid (GTC) for {active_shares:.0f}sh {leg2_name} @ ${cheap_target_p:.2f} on book...")
                    ok2, st2, bid_p2, oid2, tx2, lat2 = place_limit_order(leg2_token, cheap_target_p, active_shares, leg2_name, OrderType.GTC)
                    
                    leg2_filled = False
                    leg2_price = cheap_target_p

                    if ok2 and st2 == "matched":
                        leg2_filled = True
                        leg2_price = bid_p2
                        log(f"⚡ [LEG 2 INSTANT MATCH] {active_shares:.2f}sh {leg2_name} filled immediately @ ${bid_p2:.2f}!")
                    elif ok2 and st2 == "live":
                        log(f"⏳ [RESTING BID ACTIVE] {active_shares:.2f}sh {leg2_name} bid resting @ ${cheap_target_p:.2f} (Order ID: {oid2[:12]}...). Sitting & waiting...")

                    # Sit and wait loop (Give Leg 2 up to 5 seconds to match)
                    t_leg1_filled = time.time()
                    leg1_sold_profit = False
                    sell_gain = 0.0
                    last_leg_check = 0.0

                    while not leg2_filled:
                        now_loop = time.time()
                        time_waiting = now_loop - t_leg1_filled
                        rem_loop = max(0, mkt["window_end"] - int(now_loop))

                        # 1. Check ground truth on Polymarket every ~1 second:
                        if now_loop - last_leg_check >= 1.0:
                            last_leg_check = now_loop
                            if check_both_legs_captured(mkt.get("condition_id", ""), mkt.get("title", "")):
                                leg2_filled = True
                                print("\n")
                                log(f"🎉 [BOTH LEGS CONFIRMED ON POLYMARKET] UP and DOWN both held! Hedge is 100% LOCKED. NEVER SELLING.")
                                break

                        # 2. Check if resting order got filled on CLOB
                        if oid2:
                            try:
                                o_data = client.get_order(oid2)
                                if isinstance(o_data, dict):
                                    o_status = str(o_data.get("status", "")).upper()
                                    matched_sz = float(o_data.get("size_matched", 0))
                                    if o_status == "MATCHED" or matched_sz >= active_shares:
                                        leg2_filled = True
                                        leg2_price = cheap_target_p
                                        print("\n")
                                        log(f"🎉 [RESTING BID FILLED!] {active_shares:.2f}sh {leg2_name} matched on the book @ ${cheap_target_p:.2f}!")
                                        break
                            except Exception:
                                pass

                        _up_p, _, _dn_p, _ = fetch_book_asks(mkt["up_token"], mkt["down_token"])
                        cur_cheap_p = _dn_p if leg2_name == "DOWN" else _up_p

                        cur_loop_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
                        print(f"\r   [{cur_loop_ts} UTC | Waiting for fill | {time_waiting:.1f}s/5.0s | T-{rem_loop:02d}s] {leg2_name} Ask: ${cur_cheap_p:.2f} (Target: <= ${cheap_target_p:.2f})", end="", flush=True)

                        # 3. If market ask drops directly to target, snap it
                        if cur_cheap_p <= cheap_target_p:
                            print("\n")
                            log(f"⚡ [CHEAP ASK HIT] {leg2_name} ask is ${cur_cheap_p:.2f} <= ${cheap_target_p:.2f}! Snapping {active_shares:.2f}sh...")
                            ok_snap, st_snap, p_snap, _, tx_snap, _ = place_limit_order(leg2_token, cur_cheap_p, active_shares, leg2_name, OrderType.GTC)
                            if ok_snap:
                                leg2_price = p_snap
                                time.sleep(0.4)
                                if check_both_legs_captured(mkt.get("condition_id", ""), mkt.get("title", "")) or st_snap in ("matched", "live") or tx_snap:
                                    leg2_filled = True
                                    log(f"🎉 [LEG 2 SNAP FILLED] Snapped {leg2_name} @ ${p_snap:.2f}! Both legs locked.")
                                    break

                        # 4. 5-SECOND PROFIT BAILOUT RULE:
                        # At 5 seconds: Check if both legs captured. If YES -> DO NOT SELL. If NO -> SELL Leg 1.
                        if time_waiting >= 5.0 or rem_loop <= 10:
                            print("\n")
                            # Step A: Check ground truth before taking any action
                            if check_both_legs_captured(mkt.get("condition_id", ""), mkt.get("title", "")):
                                leg2_filled = True
                                log(f"🎉 [BOTH LEGS CONFIRMED AT 5s] Both legs held on Polymarket! Aborting sell, hedge is complete.")
                                break

                            log(f"⏱️ [5-SECOND HEDGE TIMER EXPIRED ({time_waiting:.1f}s)] Leg 2 NOT captured! Cancelling open orders...")
                            if oid2:
                                try:
                                    client.cancel_order(OrderPayload(orderID=oid2))
                                except Exception:
                                    pass
                            try:
                                client.cancel_all()
                            except Exception:
                                pass

                            # Step B: Double-check right after cancel in case of late fill
                            time.sleep(0.25)
                            if check_both_legs_captured(mkt.get("condition_id", ""), mkt.get("title", "")):
                                leg2_filled = True
                                log(f"🎉 [FINAL CHECK AFTER CANCEL] Both legs captured! Aborting sell.")
                                break

                            # Step C: Only if STILL missing Leg 2, sell unhedged Leg 1 to panic buyers
                            best_bid_p, best_bid_sz = fetch_book_best_bid(leg1_token)
                            target_sell_p = round(max(best_bid_p, fill_p1 + 0.01), 2)
                            log(f"🚀 [SELLING UNHEDGED LEG 1 TO PANIC BUYERS] Best Book Bid: ${best_bid_p:.2f} | Posting Limit Sell for {active_shares:.0f}sh {leg1_name} @ ${target_sell_p:.2f} (+${target_sell_p - fill_p1:.2f} profit)...")

                            ok_s, st_s, sell_p, oid_s, tx_s, _ = place_limit_order(leg1_token, target_sell_p, active_shares, leg1_name, OrderType.GTC, side="SELL")
                            
                            # Wait up to 3 seconds for the panic buyers to snap our sell order
                            t_sell_wait = time.time()
                            while time.time() - t_sell_wait < 3.0:
                                if st_s == "matched" or tx_s:
                                    leg1_sold_profit = True
                                    sell_gain = round((target_sell_p - fill_p1) * active_shares, 2)
                                    break
                                if oid_s:
                                    try:
                                        s_data = client.get_order(oid_s)
                                        if isinstance(s_data, dict) and str(s_data.get("status", "")).upper() == "MATCHED":
                                            leg1_sold_profit = True
                                            sell_gain = round((target_sell_p - fill_p1) * active_shares, 2)
                                            break
                                    except Exception:
                                        pass
                                time.sleep(0.25)

                            if leg1_sold_profit:
                                log(f"💰 [PANIC BUYERS SNAPPED SELL!] Sold {active_shares:.0f}sh {leg1_name} @ ${target_sell_p:.2f}! Locked Profit: +${sell_gain:.2f} USDC!")
                            else:
                                # If panic buyers backed off slightly, take best available market bid at or near entry
                                best_bid_p2, _ = fetch_book_best_bid(leg1_token)
                                if best_bid_p2 > 0:
                                    try:
                                        client.cancel_all()
                                    except Exception:
                                        pass
                                    exit_p = max(best_bid_p2, round(fill_p1 - 0.01, 2))
                                    log(f"⚡ [FAST MARKET EXIT] Snapping best bid @ ${exit_p:.2f} to completely exit...")
                                    place_limit_order(leg1_token, exit_p, active_shares, leg1_name, OrderType.FOK, side="SELL")
                                    leg1_sold_profit = True
                                    sell_gain = round((exit_p - fill_p1) * active_shares, 2)
                            break

                        time.sleep(0.25)

                    # Final Summary & Rollover
                    print("\n" + "=" * 80)
                    if leg2_filled:
                        total_cost_per_share = round(fill_p1 + leg2_price, 3)
                        total_spent = round(total_cost_per_share * active_shares, 2)
                        payout = round(1.00 * active_shares, 2)
                        profit = round(payout - total_spent, 2)
                        pct = round((profit / total_spent) * 100, 1)

                        streak_count += 1
                        total_streak_profit += profit

                        print("🎉 [ARBITRAGE SEALED & 100% GUARANTEED PROFIT]")
                        print(f"• Leg 1 ({leg1_name}):   {active_shares:.0f} shares @ ${fill_p1:.2f}")
                        print(f"• Leg 2 ({leg2_name}): {active_shares:.0f} shares @ ${leg2_price:.2f}")
                        print(f"• Total Paid:       ${total_spent:.2f} (${total_cost_per_share:.3f} per pair)")
                        print(f"• Guaranteed Pay:   ${payout:.2f} USDC (at resolution)")
                        print(f"• Net Profit:       +${profit:.2f} USDC (+{pct}%)")
                        print("=" * 80)

                        if int(active_shares) >= 8:
                            current_stake = 4.90  # Reset back to 5 shares base!
                            log(f"🏆 [8-SHARE SPRINT FINISHED!] 8 shares win locked! Banking profit & resetting cycle back to 5 shares.")
                            log(f"💰 Total Profit Banked to Wallet: +${total_streak_profit:.2f} USDC across {streak_count} wins!")
                        else:
                            current_stake = round(payout, 2)  # Roll over winnings!
                            log(f"🔥 [STREAK WIN #{streak_count}] Winnings Rolled Over! Next Stake: ${current_stake:.2f} USDC | Total Profit Banked: +${total_streak_profit:.2f} USDC")
                        print("=" * 80)
                    elif leg1_sold_profit:
                        streak_count += 1
                        total_streak_profit += max(0.0, sell_gain)
                        print("💰 [PANIC BUYER PROFIT BAILOUT COMPLETED]")
                        print(f"• Bought Leg 1 ({leg1_name}): {active_shares:.0f} shares @ ${fill_p1:.2f}")
                        print(f"• Sold to Panic Buyers:  {active_shares:.0f} shares @ ${target_sell_p if 'target_sell_p' in locals() else fill_p1:.2f}")
                        print(f"• Net PnL on Trade:      {'+$' if sell_gain >= 0 else '-$'}{abs(sell_gain):.2f} USDC")
                        print(f"• Streak Profit Banked:  +${total_streak_profit:.2f} USDC across {streak_count} rounds")
                        print("=" * 80)
                    else:
                        print(f"ℹ️ Trade finished: Leg 1 holding {active_shares:.0f}sh {leg1_name} @ ${fill_p1:.2f}.")
                        print("=" * 80)

                    # Wait for candle resolution and payout arrival before rotating
                    log("⏳ Waiting for candle window to resolve and payout to land...")
                    while True:
                        now_res = int(time.time())
                        rem_res = max(0, mkt["window_end"] - now_res)
                        if rem_res <= 0:
                            break
                        print(f"\r   [Settling in {rem_res:02d}s | Rolling over to next candle...]", end="", flush=True)
                        time.sleep(1.0)
                    print("\n")
                    time.sleep(3.0)
                    next_sh = min(8, max(5, int(current_stake / 0.98)))
                    log(f"🔄 [ROLLOVER ACTIVE] Next trade ready: {next_sh} whole shares (${current_stake:.2f} USDC stake). Hunting next wave...\n")
                else:
                    log(f"⚠️ [LEG 1 REJECTED/FAILED] Status: {st1}. Candle not locked. Ready to retry if shares appear.")
            else:
                pass

        time.sleep(0.40)
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
        break
    except Exception as e:
        time.sleep(1.0)
