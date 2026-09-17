import requests
import time
import datetime
import sys
import json

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"
TARGET_ASSET = "eth"
ORDER_SIZE = 5.0
LEG1_MAX_PRICE = 0.45
MAX_PAIR_COST = 0.99

# Simulated Paper Wallet
paper_balance = 10.00
starting_balance = 10.00
lifetime_pairs = 0
lifetime_profit = 0.0

print("=" * 70)
print("  POLYBOT 100% RISKLESS PAPER ARBITRAGE SIMULATOR (ETH 5M)")
print("  Mode: Zero Real Money | Live Polymarket Orderbooks | Live Ticker")
print(f"  Starting Virtual Wallet: ${paper_balance:.2f} USDC | Order Size: {ORDER_SIZE:.0f} shares")
print("=" * 70)

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
session.mount("https://", adapter)

def get_active_market():
    now = int(time.time())
    cur_w = (now // 300) * 300
    for w_s in [cur_w, cur_w + 300]:
        slug = f"{TARGET_ASSET}-updown-5m-{w_s}"
        try:
            r = session.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
            if r and r[0].get("markets"):
                m = r[0]["markets"][0]
                tokens = json.loads(m.get("clobTokenIds", "[]"))
                if len(tokens) >= 2 and now < (w_s + 300):
                    return {
                        "slug": slug,
                        "title": r[0].get("title", slug),
                        "window_start": w_s,
                        "window_end": w_s + 300,
                        "up_token": tokens[0],
                        "down_token": tokens[1]
                    }
        except Exception:
            pass
    return None

def fetch_books(up_tok, dn_tok):
    try:
        r_up = session.get(f"{CLOB_HOST}/book?token_id={up_tok}", timeout=1.5).json()
        r_dn = session.get(f"{CLOB_HOST}/book?token_id={dn_tok}", timeout=1.5).json()
        
        asks_up = r_up.get("asks", [])
        asks_dn = r_dn.get("asks", [])
        
        best_up = min(asks_up, key=lambda x: float(x["price"])) if asks_up else None
        best_dn = min(asks_dn, key=lambda x: float(x["price"])) if asks_dn else None
        
        up_p = float(best_up["price"]) if best_up else 1.0
        up_s = float(best_up["size"]) if best_up else 0.0
        dn_p = float(best_dn["price"]) if best_dn else 1.0
        dn_s = float(best_dn["size"]) if best_dn else 0.0
        
        return up_p, up_s, dn_p, dn_s
    except Exception:
        return 1.0, 0.0, 1.0, 0.0

current_mkt = None
leg1_position = None
leg2_position = None
trades_in_candle = 0

last_ticker_time = 0

while True:
    try:
        now = int(time.time())
        if not current_mkt or now >= current_mkt["window_end"]:
            # Evaluate last candle outcome
            if leg1_position and leg2_position:
                pair_cost = leg1_position["price"] + leg2_position["price"]
                payout = ORDER_SIZE * 1.00 # One side always pays out $1.00
                total_invested = round(pair_cost * ORDER_SIZE, 3)
                net_profit = round(payout - total_invested, 3)
                paper_balance += net_profit
                lifetime_profit += net_profit
                lifetime_pairs += 1
                print("\n" + "=" * 70)
                print(f"💰 [CANDLE RESOLUTION & PAYOUT] {current_mkt['slug']}")
                print(f"   Invested: ${total_invested:.2f} | Guaranteed Payout: ${payout:.2f}")
                print(f"   Net Profit Earned: +${net_profit:.3f} | Virtual Balance: ${paper_balance:.2f}")
                print(f"   Total Lifetime Pairs Completed: {lifetime_pairs} | Total Profit: +${lifetime_profit:.3f}")
                print("=" * 70 + "\n")
            elif leg1_position and not leg2_position:
                print(f"\n⚠️ [CANDLE EXPIRED UNHEDGED] Never filled Leg 2! Holding {leg1_position['outcome']} into settlement.\n")

            current_mkt = get_active_market()
            leg1_position = None
            leg2_position = None
            trades_in_candle = 0
            if current_mkt:
                end_str = datetime.datetime.fromtimestamp(current_mkt["window_end"], tz=datetime.timezone.utc).strftime("%H:%M:%S UTC")
                print(f"\n🟢 [NEW 5M CANDLE] {current_mkt['slug']} (Resolves at {end_str})")
                print(f"   Virtual Balance Available: ${paper_balance:.2f} USDC\n")
            else:
                time.sleep(2.0)
                continue
                
        t_rem = max(0, current_mkt["window_end"] - int(time.time()))
        up_p, up_s, dn_p, dn_s = fetch_books(current_mkt["up_token"], current_mkt["down_token"])
        comb = round(up_p + dn_p, 3)
        
        # State 1: Looking for Leg 1 (Price <= $0.45, Depth >= 5 shares)
        if leg1_position is None and trades_in_candle == 0 and t_rem > 45:
            # Check UP
            if up_p <= LEG1_MAX_PRICE and up_s >= ORDER_SIZE:
                pair_cost_est = round(ORDER_SIZE * MAX_PAIR_COST, 2)
                # Solvency Guard
                if paper_balance >= pair_cost_est:
                    leg1_position = {
                        "outcome": "UP",
                        "price": up_p,
                        "shares": ORDER_SIZE,
                        "time": now,
                        "max_opp_price": round(MAX_PAIR_COST - up_p, 3)
                    }
                    cost_spent = round(ORDER_SIZE * up_p, 2)
                    print(f"\n🎯 [PAPER LEG 1 FILLED] Bought {ORDER_SIZE:.0f} UP @ ${up_p:.2f} (-${cost_spent:.2f}) | Depth: {up_s:.0f}sh | T-{t_rem}s")
                    print(f"🏹 [HUNTING LEG 2] Need DOWN @ <= ${leg1_position['max_opp_price']:.2f} to guarantee profit!\n")
                else:
                    if now % 5 == 0:
                        print(f"⚠️ [SOLVENCY GUARD] Balance (${paper_balance:.2f}) < required (${pair_cost_est:.2f}). Skipping.")

            # Check DOWN
            elif dn_p <= LEG1_MAX_PRICE and dn_s >= ORDER_SIZE:
                pair_cost_est = round(ORDER_SIZE * MAX_PAIR_COST, 2)
                if paper_balance >= pair_cost_est:
                    leg1_position = {
                        "outcome": "DOWN",
                        "price": dn_p,
                        "shares": ORDER_SIZE,
                        "time": now,
                        "max_opp_price": round(MAX_PAIR_COST - dn_p, 3)
                    }
                    cost_spent = round(ORDER_SIZE * dn_p, 2)
                    print(f"\n🎯 [PAPER LEG 1 FILLED] Bought {ORDER_SIZE:.0f} DOWN @ ${dn_p:.2f} (-${cost_spent:.2f}) | Depth: {dn_s:.0f}sh | T-{t_rem}s")
                    print(f"🏹 [HUNTING LEG 2] Need UP @ <= ${leg1_position['max_opp_price']:.2f} to guarantee profit!\n")
                else:
                    if now % 5 == 0:
                        print(f"⚠️ [SOLVENCY GUARD] Balance (${paper_balance:.2f}) < required (${pair_cost_est:.2f}). Skipping.")
                
        # State 2: Holding Leg 1, hunting for Leg 2
        elif leg1_position is not None and leg2_position is None:
            needed_price = leg1_position["max_opp_price"]
            
            if leg1_position["outcome"] == "UP":
                # Need DOWN
                if dn_p <= needed_price and dn_s >= ORDER_SIZE:
                    delay = now - leg1_position["time"]
                    leg2_position = {
                        "outcome": "DOWN",
                        "price": dn_p,
                        "shares": ORDER_SIZE,
                        "delay": delay
                    }
                    trades_in_candle += 1
                    total_comb = round(leg1_position["price"] + dn_p, 3)
                    total_stake = round(total_comb * ORDER_SIZE, 3)
                    locked_profit = round((1.0 - total_comb) * ORDER_SIZE, 3)
                    pct = round(((1.0 - total_comb) / total_comb) * 100, 1)
                    
                    print(f"\n🎉 [PAPER LEG 2 FILLED after {delay}s] Bought {ORDER_SIZE:.0f} DOWN @ ${dn_p:.2f}! | Depth: {dn_s:.0f}sh | T-{t_rem}s")
                    print(f"🔒 [PAIR LOCKED & 100% HEDGED] Total Stake: ${total_stake:.2f} | Payout: ${ORDER_SIZE:.2f} | Locked Profit: +${locked_profit:.3f} (+{pct}%)\n")
            else:
                # Need UP
                if up_p <= needed_price and up_s >= ORDER_SIZE:
                    delay = now - leg1_position["time"]
                    leg2_position = {
                        "outcome": "UP",
                        "price": up_p,
                        "shares": ORDER_SIZE,
                        "delay": delay
                    }
                    trades_in_candle += 1
                    total_comb = round(leg1_position["price"] + up_p, 3)
                    total_stake = round(total_comb * ORDER_SIZE, 3)
                    locked_profit = round((1.0 - total_comb) * ORDER_SIZE, 3)
                    pct = round(((1.0 - total_comb) / total_comb) * 100, 1)
                    
                    print(f"\n🎉 [PAPER LEG 2 FILLED after {delay}s] Bought {ORDER_SIZE:.0f} UP @ ${up_p:.2f}! | Depth: {up_s:.0f}sh | T-{t_rem}s")
                    print(f"🔒 [PAIR LOCKED & 100% HEDGED] Total Stake: ${total_stake:.2f} | Payout: ${ORDER_SIZE:.2f} | Locked Profit: +${locked_profit:.3f} (+{pct}%)\n")

        # Console ticker every 2.0s
        if time.time() - last_ticker_time >= 2.0:
            last_ticker_time = time.time()
            if leg1_position and not leg2_position:
                target_token = "DOWN" if leg1_position["outcome"] == "UP" else "UP"
                status_str = f"🏹 HUNTING {target_token} <= ${leg1_position['max_opp_price']:.2f}"
            elif leg1_position and leg2_position:
                status_str = "🔒 PAIR LOCKED (100% Hedged)"
            else:
                status_str = "🔍 SCANNING FOR ENTRY (<= $0.45)"
            print(f"T-{t_rem:03d}s | UP: ${up_p:.2f} ({up_s:3.0f}sh) | DN: ${dn_p:.2f} ({dn_s:3.0f}sh) | Sum: ${comb:.3f} | {status_str}")
            
        time.sleep(0.15)
    except KeyboardInterrupt:
        print("\nSimulator stopped by user.")
        break
    except Exception as e:
        time.sleep(0.5)
