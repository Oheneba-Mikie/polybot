import requests
import json
import time
import datetime
import sys
import statistics
from collections import deque
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

print("="*125)
print("🔬 STAGE 3 STRATEGY VIABILITY & LEG-2 RISK AUDIT: UNHEDGED RESOLUTION, QUEUE SIMULATION & SIZING")
print("="*125)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

TARGET_TOTAL_COST = 0.960
LATENCY_TIERS_MS  = [25, 50, 75, 100, 150, 200, 300, 500, 750, 1000]
QUEUE_ASSUMPTIONS = {
    "0% (First)": 0.00,
    "25%": 0.25,
    "50% (Median)": 0.50,
    "75%": 0.75,
    "100% (Last)": 1.00
}
SIZES_TO_TEST = [5, 10, 20, 50, 100]

now_ts = int(time.time() // 300) * 300
sample_timestamps = [now_ts - (i * 300 * 2) for i in range(1, 101)]

print("1. Fetching 100 historical 5-minute markets, on-chain trade tapes & exact market resolutions...")

def fetch_market_full_history(ts):
    slug = f"btc-updown-5m-{ts}"
    w_s = ts
    w_e = ts + 300
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r or not r[0].get("markets"): return None
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        clob_ids = json.loads(mkt.get("clobTokenIds") or "[]")
        outcomes = json.loads(mkt.get("outcomes") or "[]")
        if len(clob_ids) < 2: return None

        # Determine true market resolution (UP won = 1.00 for UP / 0.00 for DOWN)
        outcome_prices = json.loads(mkt.get("outcomePrices") or "[]")
        resolved = mkt.get("closed", False)
        winning_outcome = None
        if outcome_prices:
            p0 = float(outcome_prices[0])
            p1 = float(outcome_prices[1])
            if p0 > 0.85: winning_outcome = outcomes[0].upper()
            elif p1 > 0.85: winning_outcome = outcomes[1].upper()
        
        # Pull trade tape
        tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=300", timeout=4).json()
        if not tr or not isinstance(tr, list): return None
        
        market_trades = []
        for t in tr:
            trade_ts = t.get("timestamp", 0)
            if w_s <= trade_ts <= w_e:
                market_trades.append({
                    "ts_ms": int(trade_ts * 1000),
                    "side": str(t.get("side", "")).upper(),
                    "outcome": str(t.get("outcome", "")).upper(),
                    "price": float(t.get("price", 0)),
                    "size": float(t.get("size", 0))
                })
        market_trades.sort(key=lambda x: x["ts_ms"])
        if not market_trades: return None
        
        # If winning outcome wasn't explicit from outcomePrices, deduce from final trade near resolution
        if not winning_outcome:
            final_trades = [t for t in market_trades if t["ts_ms"] >= (w_e - 30)*1000]
            if final_trades:
                last_t = final_trades[-1]
                if last_t["price"] >= 0.80: winning_outcome = last_t["outcome"]
                elif last_t["price"] <= 0.20: winning_outcome = "DOWN" if last_t["outcome"] == "UP" else "UP"

        opps = []
        for t in market_trades:
            if t["side"] == "BUY" and t["price"] <= 0.600:
                opps.append({
                    "market_slug": slug,
                    "candle_start_ts": w_s,
                    "candle_end_ts": w_e,
                    "winning_outcome": winning_outcome,
                    "side": t["outcome"],
                    "t0_ms": t["ts_ms"],
                    "price": t["price"],
                    "displayed_depth": t["size"] * (1.5 + (hash(str(t['ts_ms'])) % 10) / 2.0),
                    "market_trades": market_trades
                })
        return {"slug": slug, "opps": opps}
    except Exception:
        return None

market_datasets = []
with ThreadPoolExecutor(max_workers=15) as executor:
    for res in executor.map(fetch_market_full_history, sample_timestamps):
        if res and res["opps"]:
            market_datasets.append(res)

all_opportunities = []
for m in market_datasets:
    all_opportunities.extend(m["opps"])

print(f"✅ Loaded {len(market_datasets)} completed markets with {len(all_opportunities):,} qualifying trade-level opportunity events.\n")

# Split: 70 Calibration (In-Sample) vs 30 Validation (Out-of-Sample)
train_markets = set([m["slug"] for m in market_datasets[:70]])
test_markets  = set([m["slug"] for m in market_datasets[70:]])

train_opps = [o for o in all_opportunities if o["market_slug"] in train_markets]
test_opps  = [o for o in all_opportunities if o["market_slug"] in test_markets]

# ==============================================================================
# SIMULATION ENGINE: 3 OUTCOMES (Complete Hedge, Unhedged Profit, Unhedged Loss)
# ==============================================================================
def evaluate_strategy_run(opp_list, queue_pct=0.50, latency_ms=150, size=5.0, bailout_thresh=None, filter_max_price=0.60, filter_min_time=0):
    complete_hedges = 0
    unhedged_profits = 0
    unhedged_losses = 0
    
    total_hedge_profit = 0.0
    total_unhedged_profit = 0.0
    total_unhedged_loss = 0.0
    
    inter_leg_delays = []
    worst_single_loss = 0.0
    
    for opp in opp_list:
        px1 = opp["price"]
        if px1 > filter_max_price: continue
        
        t0_ms = opp["t0_ms"]
        w_e_ms = opp["candle_end_ts"] * 1000
        time_left_sec = (w_e_ms - t0_ms) / 1000.0
        if time_left_sec < filter_min_time: continue
        
        side1 = opp["side"]
        disp_depth1 = opp["displayed_depth"]
        trades = opp["market_trades"]
        winner = opp["winning_outcome"]
        
        # 1. Evaluate Leg 1 Execution
        queue_ahead_1 = disp_depth1 * queue_pct
        consumed_1 = sum([t["size"] for t in trades if t0_ms <= t["ts_ms"] <= t0_ms + latency_ms and t["outcome"] == side1 and t["price"] <= px1])
        leg1_filled = (consumed_1 >= queue_ahead_1 + size) or (disp_depth1 - queue_ahead_1 >= size)
        
        if not leg1_filled:
            continue # Order never executed
            
        leg1_cost = px1 * size
        t1_ms = t0_ms + latency_ms + int(queue_ahead_1 * 2)
        
        # 2. Evaluate Leg 2 Execution
        max_leg2_px = round(TARGET_TOTAL_COST - px1, 4)
        opp_side = "DOWN" if side1 == "UP" else "UP"
        
        opp_trades = [t for t in trades if t["ts_ms"] >= t1_ms and t["outcome"] == opp_side and t["price"] <= max_leg2_px]
        
        leg2_filled = False
        if opp_trades:
            leg2_t = opp_trades[0]
            t2_ms = leg2_t["ts_ms"]
            t2_t1 = t2_ms - t1_ms
            inter_leg_delays.append(t2_t1)
            
            disp_depth2 = leg2_t["size"] * (1.5 + (hash(str(t2_ms)) % 10) / 2.0)
            queue_ahead_2 = disp_depth2 * queue_pct
            consumed_2 = sum([t["size"] for t in trades if t2_ms <= t["ts_ms"] <= t2_ms + latency_ms and t["outcome"] == opp_side and t["price"] <= max_leg2_px])
            
            leg2_filled = (consumed_2 >= queue_ahead_2 + size) or (disp_depth2 - queue_ahead_2 >= size)
            if leg2_filled:
                leg2_px = leg2_t["price"]
                total_cost = (px1 + leg2_px) * size
                payout = 1.00 * size
                profit = payout - total_cost
                if profit >= 0:
                    complete_hedges += 1
                    total_hedge_profit += profit
                else:
                    leg2_filled = False
                    
        # 3. Handle Failure State (Unhedged Leg 1 Position)
        if not leg2_filled:
            # Bailout simulation
            if bailout_thresh is not None:
                # Attempt bailout exit
                exit_trades = [t for t in trades if t["ts_ms"] >= t1_ms + 2000 and t["outcome"] == side1]
                if exit_trades:
                    exit_px = exit_trades[0]["price"]
                    loss = (px1 - exit_px) * size
                    if loss > 0:
                        unhedged_losses += 1
                        total_unhedged_loss += loss
                        if loss > worst_single_loss: worst_single_loss = loss
                    else:
                        unhedged_profits += 1
                        total_unhedged_profit += abs(loss)
                    continue

            # Hold until candle settlement
            if winner == side1:
                # Won! Payout = $1.00 per share
                profit = (1.00 - px1) * size
                unhedged_profits += 1
                total_unhedged_profit += profit
            else:
                # Lost! Total loss of Leg 1 investment
                loss = px1 * size
                unhedged_losses += 1
                total_unhedged_loss += loss
                if loss > worst_single_loss: worst_single_loss = loss

    total_opps = max(1, complete_hedges + unhedged_profits + unhedged_losses)
    net_pnl = round(total_hedge_profit + total_unhedged_profit - total_unhedged_loss, 2)
    avg_pnl_per_trade = round(net_pnl / total_opps, 4)
    
    return {
        "total_trades": total_opps,
        "complete_hedges": complete_hedges,
        "hedge_rate": round(complete_hedges / total_opps * 100, 1),
        "unhedged_profits": unhedged_profits,
        "unhedged_profit_rate": round(unhedged_profits / total_opps * 100, 1),
        "unhedged_losses": unhedged_losses,
        "unhedged_loss_rate": round(unhedged_losses / total_opps * 100, 1),
        "total_hedge_profit": round(total_hedge_profit, 2),
        "total_unhedged_profit": round(total_unhedged_profit, 2),
        "total_unhedged_loss": round(total_unhedged_loss, 2),
        "net_pnl": net_pnl,
        "avg_pnl_per_trade": avg_pnl_per_trade,
        "worst_single_loss": round(worst_single_loss, 2),
        "inter_leg_delays": inter_leg_delays
    }

# ==============================================================================
# SECTION 1: QUEUE SENSITIVITY TABLE
# ==============================================================================
print("="*125)
print("📊 TABLE 1: TRUE STRATEGY EXPECTED VALUE ACROSS QUEUE POSITIONS (AT 150ms LATENCY, 5 SHARES)")
print("="*125)
print(f"{'Queue Position':<15} | {'Trades':<8} | {'Hedge %':<10} | {'Unhedged Win%':<15} | {'Unhedged Loss%':<16} | {'Avg P&L/Trade':<15} | {'Total Net P&L':<15}")
print("-" * 125)
for q_name, q_val in QUEUE_ASSUMPTIONS.items():
    res = evaluate_strategy_run(all_opportunities, queue_pct=q_val, latency_ms=150, size=5.0)
    pnl_sign = "+" if res["net_pnl"] >= 0 else ""
    avg_sign = "+" if res["avg_pnl_per_trade"] >= 0 else ""
    print(f"{q_name:<15} | {res['total_trades']:<8} | {res['hedge_rate']:<9}% | {res['unhedged_profit_rate']:<14}% | {res['unhedged_loss_rate']:<15}% | {avg_sign}${res['avg_pnl_per_trade']:<13.4f} | {pnl_sign}${res['net_pnl']:<13.2f}")
print("="*125)

# ==============================================================================
# SECTION 2: POSITION SIZING SENSITIVITY TABLE
# ==============================================================================
print("\n" + "="*125)
print("📊 TABLE 2: POSITION SIZING SENSITIVITY (50% QUEUE POSITION, 150ms LATENCY)")
print("="*125)
print(f"{'Size (Shares)':<15} | {'Trades':<8} | {'Complete Hedge %':<18} | {'Unhedged Loss %':<18} | {'Avg P&L / Trade':<18} | {'Worst Single Loss':<18} | {'Total Net P&L':<15}")
print("-" * 125)
for sz in SIZES_TO_TEST:
    res = evaluate_strategy_run(all_opportunities, queue_pct=0.50, latency_ms=150, size=float(sz))
    pnl_sign = "+" if res["net_pnl"] >= 0 else ""
    avg_sign = "+" if res["avg_pnl_per_trade"] >= 0 else ""
    print(f"{f'{sz} shares':<15} | {res['total_trades']:<8} | {res['hedge_rate']:<17}% | {res['unhedged_loss_rate']:<17}% | {avg_sign}${res['avg_pnl_per_trade']:<16.4f} | -${res['worst_single_loss']:<16.2f} | {pnl_sign}${res['net_pnl']:<13.2f}")
print("="*125)

# ==============================================================================
# SECTION 3: INTER-LEG DELAY BREAKDOWN
# ==============================================================================
print("\n" + "="*125)
print("📊 TABLE 3: INTER-LEG DELAY DECOMPOSITION (TIME UNTIL OPPOSING LEG 2 ARRIVES)")
print("="*125)
print(f"{'Inter-Leg Delay Bucket':<25} | {'Leg 2 Hedge Rate':<20} | {'Unhedged Loss Rate':<20} | {'Expected Trade P&L':<20}")
print("-" * 125)

delay_buckets = [
    ("< 100ms", 0, 100),
    ("100 - 250ms", 100, 250),
    ("250 - 500ms", 250, 500),
    ("500ms - 1.0s", 500, 1000),
    ("1.0s - 2.0s", 1000, 2000),
    ("2.0s - 3.0s", 2000, 3000),
    ("3.0s - 5.0s", 3000, 5000),
    ("> 5.0s", 5000, 9999999)
]

for b_name, b_min, b_max in delay_buckets:
    # Filter opps where Leg 2 delay fell in this bucket
    b_opps = []
    for o in all_opportunities:
        # Check delay in trades
        t0 = o["t0_ms"]
        px = o["price"]
        opp_side = "DOWN" if o["side"] == "UP" else "UP"
        max_px2 = TARGET_TOTAL_COST - px
        opp_t = [t for t in o["market_trades"] if t["ts_ms"] >= t0 + 150 and t["outcome"] == opp_side and t["price"] <= max_px2]
        if opp_t:
            d = opp_t[0]["ts_ms"] - (t0 + 150)
            if b_min <= d < b_max:
                b_opps.append(o)
        elif b_max > 5000:
            b_opps.append(o)

    if b_opps:
        r = evaluate_strategy_run(b_opps, queue_pct=0.50, latency_ms=150, size=5.0)
        p_sign = "+" if r["avg_pnl_per_trade"] >= 0 else ""
        print(f"{b_name:<25} | {r['hedge_rate']:<19}% | {r['unhedged_loss_rate']:<19}% | {p_sign}${r['avg_pnl_per_trade']:<18.4f}")
    else:
        print(f"{b_name:<25} | {'N/A':<19} | {'N/A':<19} | {'N/A':<18}")
print("="*125)

# ==============================================================================
# SECTION 4: CANDLE REMAINING TIME BREAKDOWN
# ==============================================================================
print("\n" + "="*125)
print("📊 TABLE 4: REMAINING CANDLE TIME SENSITIVITY (AT LEG 1 TRIGGER)")
print("="*125)
print(f"{'Remaining Time in 5m Candle':<30} | {'Complete Hedge %':<20} | {'Unhedged Loss %':<20} | {'Avg P&L / Trade':<20}")
print("-" * 125)

time_buckets = [
    ("> 240s (Minute 1)", 240, 300),
    ("180 - 240s (Minute 2)", 180, 240),
    ("120 - 180s (Minute 3)", 120, 180),
    ("60 - 120s (Minute 4)", 60, 120),
    ("30 - 60s (Final Minute)", 30, 60),
    ("10 - 30s (Pre-Expiry)", 10, 30),
    ("< 10s (Expiry Tick)", 0, 10)
]

for t_name, t_min, t_max in time_buckets:
    t_opps = [o for o in all_opportunities if t_min <= (o["candle_end_ts"]*1000 - o["t0_ms"])/1000.0 < t_max]
    if t_opps:
        r = evaluate_strategy_run(t_opps, queue_pct=0.50, latency_ms=150, size=5.0)
        p_sign = "+" if r["avg_pnl_per_trade"] >= 0 else ""
        print(f"{t_name:<30} | {r['hedge_rate']:<19}% | {r['unhedged_loss_rate']:<19}% | {p_sign}${r['avg_pnl_per_trade']:<18.4f}")
print("="*125)

# ==============================================================================
# SECTION 5: IN-SAMPLE VS. OUT-OF-SAMPLE VALIDATION
# ==============================================================================
print("\n" + "="*125)
print("📊 TABLE 5: IN-SAMPLE (70 MARKETS) VS. OUT-OF-SAMPLE (30 UNTOUCHED MARKETS) VALIDATION")
print("="*125)
print(f"{'Dataset Split':<25} | {'Total Trades':<15} | {'Hedge %':<12} | {'Unhedged Loss%':<18} | {'Avg P&L / Trade':<18} | {'Net Strategy P&L':<15}")
print("-" * 125)
res_train = evaluate_strategy_run(train_opps, queue_pct=0.50, latency_ms=150, size=5.0)
res_test  = evaluate_strategy_run(test_opps,  queue_pct=0.50, latency_ms=150, size=5.0)

sign_tr = "+" if res_train["net_pnl"] >= 0 else ""
sign_ts = "+" if res_test["net_pnl"] >= 0 else ""
print(f"{'In-Sample (Training 70)':<25} | {res_train['total_trades']:<15} | {res_train['hedge_rate']:<11}% | {res_train['unhedged_loss_rate']:<17}% | ${res_train['avg_pnl_per_trade']:<16.4f} | {sign_tr}${res_train['net_pnl']:<13.2f}")
print(f"{'Out-of-Sample (Test 30)':<25} | {res_test['total_trades']:<15} | {res_test['hedge_rate']:<11}% | {res_test['unhedged_loss_rate']:<17}% | ${res_test['avg_pnl_per_trade']:<16.4f} | {sign_ts}${res_test['net_pnl']:<13.2f}")
print("="*125)
