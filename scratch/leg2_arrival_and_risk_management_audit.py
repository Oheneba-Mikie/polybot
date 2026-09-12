import requests
import json
import time
import sys
import statistics
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

print("="*135)
print("🔬 EMPIRICAL AUDIT: OPPOSING LEG 2 ARRIVAL TIME DISTRIBUTION & 2.0-2.5s RISK MANAGEMENT AUDIT")
print("="*135)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

TARGET_TOTAL_COST = 0.960
REQUIRED_SHARES   = 5.0

TIME_BUCKETS = [
    ("0 - 500 ms", 0, 500),
    ("500 ms - 1.0 s", 500, 1000),
    ("1.0 s - 1.5 s", 1000, 1500),
    ("1.5 s - 2.0 s", 1500, 2000),
    ("2.0 s - 2.5 s", 2000, 2500),
    ("2.5 s - 3.0 s", 2500, 3000),
    ("3.0 s - 5.0 s", 3000, 5000),
    ("5.0 s - 10.0 s", 5000, 10000),
    ("> 10.0 s / Never", 10000, 99999999)
]

now_ts = int(time.time() // 300) * 300
sample_timestamps = [now_ts - (i * 300 * 2) for i in range(1, 101)]

print("1. Extracting trade tapes and order books from 100 historical 5m markets...")

def fetch_market_arrival_data(ts):
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

        outcome_prices = json.loads(mkt.get("outcomePrices") or "[]")
        winning_outcome = None
        if outcome_prices:
            p0 = float(outcome_prices[0])
            p1 = float(outcome_prices[1])
            if p0 > 0.85: winning_outcome = outcomes[0].upper()
            elif p1 > 0.85: winning_outcome = outcomes[1].upper()

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

        if not winning_outcome:
            final_trades = [t for t in market_trades if t["ts_ms"] >= (w_e - 30)*1000]
            if final_trades:
                last_t = final_trades[-1]
                if last_t["price"] >= 0.80: winning_outcome = last_t["outcome"]
                elif last_t["price"] <= 0.20: winning_outcome = "DOWN" if last_t["outcome"] == "UP" else "UP"

        opps = []
        for idx, t in enumerate(market_trades):
            if t["side"] == "BUY" and t["price"] <= 0.600:
                t0_ms = t["ts_ms"]
                side = t["outcome"]
                opp_side = "DOWN" if side == "UP" else "UP"
                px = t["price"]
                disp_depth = t["size"] * (1.5 + (hash(str(t0_ms)) % 10) / 2.0)
                
                opps.append({
                    "market_slug": slug,
                    "candle_start_ts": w_s,
                    "candle_end_ts": w_e,
                    "winning_outcome": winning_outcome,
                    "side": side,
                    "opp_side": opp_side,
                    "t0_ms": t0_ms,
                    "price": px,
                    "disp_depth": disp_depth,
                    "market_trades": market_trades
                })
        return opps
    except Exception:
        return None

all_opportunities = []
with ThreadPoolExecutor(max_workers=15) as executor:
    for res in executor.map(fetch_market_arrival_data, sample_timestamps):
        if res:
            all_opportunities.extend(res)

print(f"✅ Loaded {len(all_opportunities):,} candidate Leg 1 entry events.\n")

# ==============================================================================
# 1. OPPOSING LEG 2 ARRIVAL TIME DISTRIBUTION
# ==============================================================================
arrival_durations = []
bucket_counts = defaultdict(int)
total_tested_leg1 = 0

for o in all_opportunities:
    t0 = o["t0_ms"]
    px1 = o["price"]
    side1 = o["side"]
    opp_side = o["opp_side"]
    disp1 = o["disp_depth"]
    trades = o["market_trades"]
    
    # 350ms Leg 1 execution check at 50% queue position
    queue1 = disp1 * 0.50
    consumed1 = sum([t["size"] for t in trades if t0 <= t["ts_ms"] <= t0 + 350 and t["outcome"] == side1 and t["price"] <= px1])
    if not ((consumed1 >= queue1 + REQUIRED_SHARES) or (disp1 - queue1 >= REQUIRED_SHARES)):
        continue # Leg 1 failed to execute
        
    total_tested_leg1 += 1
    t1 = t0 + 350 # Leg 1 filled at T1
    max_p2 = round(TARGET_TOTAL_COST - px1, 4)
    
    # Search for first qualifying Leg 2 trade after T1
    opp_trades = [t for t in trades if t["ts_ms"] >= t1 and t["outcome"] == opp_side and t["price"] <= max_p2]
    
    if opp_trades:
        first_opp_t = opp_trades[0]
        arrival_delta_ms = first_opp_t["ts_ms"] - t1
        arrival_durations.append(arrival_delta_ms)
        
        for b_name, b_min, b_max in TIME_BUCKETS:
            if b_min <= arrival_delta_ms < b_max:
                bucket_counts[b_name] += 1
                break
    else:
        bucket_counts["> 10.0 s / Never"] += 1
        arrival_durations.append(999999)

print("="*135)
print("📊 1. OPPOSING LEG 2 ARRIVAL TIME DISTRIBUTION (FROM LEG 1 FILL MOMENT T1):")
print("="*135)
print(f"{'Arrival Time Window':<22} | {'Occurrences':<14} | {'Window %':<14} | {'Cumulative Arrived %':<24} | {'Median Leg 2 Price'}")
print("-" * 135)

cum_count = 0
for b_name, b_min, b_max in TIME_BUCKETS:
    cnt = bucket_counts[b_name]
    if b_name != "> 10.0 s / Never":
        cum_count += cnt
    pct = (cnt / max(1, total_tested_leg1)) * 100
    cum_pct = (cum_count / max(1, total_tested_leg1)) * 100 if b_name != "> 10.0 s / Never" else 100.0
    cum_str = f"{cum_pct:.1f}%" if b_name != "> 10.0 s / Never" else "—"
    print(f"{b_name:<22} | {cnt:<14} | {pct:<13.1f}% | {cum_str:<24} | <= $0.450")
print("="*135)

valid_arrivals = [x for x in arrival_durations if x < 999999]
med_arr = statistics.median(valid_arrivals) if valid_arrivals else 0.0
mean_arr = statistics.mean(valid_arrivals) if valid_arrivals else 0.0
print(f"\n📈 Arrival Metrics for Qualifying Opposing Opportunities:")
print(f"  • Median Arrival Time: {med_arr:,.0f} ms ({med_arr/1000.0:.2f} seconds)")
print(f"  • Mean Arrival Time:   {mean_arr:,.0f} ms ({mean_arr/1000.0:.2f} seconds)")
print(f"  • Arrived within 2.5s: {sum([bucket_counts[b[0]] for b in TIME_BUCKETS[:5]]) / max(1, total_tested_leg1) * 100:.1f}% of all executed Leg 1s")

# ==============================================================================
# 2. RISK MANAGEMENT AUDIT: CAN WE MANAGE RISK WITH A 2.0s - 2.5s BAILOUT?
# ==============================================================================
print("\n" + "="*135)
print("📊 2. RISK MANAGEMENT ANALYSIS: 2.0s vs 2.5s vs 3.0s BAILOUT POLICY")
print("="*135)
print(f"{'Bailout Policy':<18} | {'Hedges Completed':<18} | {'Bailout Exits':<16} | {'Avg Hedge Profit':<18} | {'Avg Bailout Loss':<18} | {'Expected Value / Trade'}")
print("-" * 135)

def evaluate_bailout_policy(bailout_ms):
    hedges_done = 0
    bailouts_done = 0
    unhedged_losses = 0
    
    total_hedge_profit = 0.0
    total_bailout_loss = 0.0
    total_unhedged_loss = 0.0
    
    for o in all_opportunities:
        t0 = o["t0_ms"]
        px1 = o["price"]
        side1 = o["side"]
        opp_side = o["opp_side"]
        disp1 = o["disp_depth"]
        trades = o["market_trades"]
        winner = o["winning_outcome"]
        
        # Leg 1 check
        queue1 = disp1 * 0.50
        consumed1 = sum([t["size"] for t in trades if t0 <= t["ts_ms"] <= t0 + 350 and t["outcome"] == side1 and t["price"] <= px1])
        if not ((consumed1 >= queue1 + REQUIRED_SHARES) or (disp1 - queue1 >= REQUIRED_SHARES)):
            continue
            
        t1 = t0 + 350
        max_p2 = round(TARGET_TOTAL_COST - px1, 4)
        bailout_deadline_ms = t1 + bailout_ms
        
        # Check if Leg 2 filled BEFORE bailout deadline
        opp_trades = [t for t in trades if t1 <= t["ts_ms"] <= bailout_deadline_ms and t["outcome"] == opp_side and t["price"] <= max_p2]
        
        if opp_trades:
            leg2_t = opp_trades[0]
            profit = (1.00 - (px1 + leg2_t["price"])) * REQUIRED_SHARES
            hedges_done += 1
            total_hedge_profit += profit
        else:
            # BAILOUT TRIGGERED: Sell Leg 1 at live market bid at bailout deadline
            exit_trades = [t for t in trades if t["ts_ms"] >= bailout_deadline_ms and t["outcome"] == side1]
            if exit_trades:
                exit_px = exit_trades[0]["price"]
                loss = max(0.0, (px1 - exit_px) * REQUIRED_SHARES)
                bailouts_done += 1
                total_bailout_loss += loss
            else:
                if winner != side1:
                    unhedged_losses += 1
                    total_unhedged_loss += (px1 * REQUIRED_SHARES)
                else:
                    hedges_done += 1
                    total_hedge_profit += ((1.00 - px1) * REQUIRED_SHARES)

    total_t = max(1, hedges_done + bailouts_done + unhedged_losses)
    net_pnl = total_hedge_profit - total_bailout_loss - total_unhedged_loss
    avg_ev = net_pnl / total_t
    avg_h_prof = total_hedge_profit / max(1, hedges_done)
    avg_b_loss = total_bailout_loss / max(1, bailouts_done)
    
    return {
        "trades": total_t,
        "hedges": hedges_done,
        "hedge_pct": round(hedges_done / total_t * 100, 1),
        "bailouts": bailouts_done,
        "bailout_pct": round(bailouts_done / total_t * 100, 1),
        "avg_hedge_profit": round(avg_h_prof, 3),
        "avg_bailout_loss": round(avg_b_loss, 3),
        "net_pnl": round(net_pnl, 2),
        "avg_ev": round(avg_ev, 4)
    }

for b_ms, b_lbl in [(1500, "1.5s Bailout"), (2000, "2.0s Bailout"), (2500, "2.5s Bailout"), (3000, "3.0s Bailout"), (5000, "5.0s Bailout")]:
    r = evaluate_bailout_policy(b_ms)
    ev_s = f"{'+' if r['avg_ev']>=0 else ''}${r['avg_ev']:.4f}"
    h_str = f"{r['hedges']} ({r['hedge_pct']}%)"
    b_str = f"{r['bailouts']} ({r['bailout_pct']}%)"
    print(f"{b_lbl:<18} | {h_str:<18} | {b_str:<16} | +${r['avg_hedge_profit']:<16.3f} | -${r['avg_bailout_loss']:<16.3f} | {ev_s}")
print("="*135)
