import requests
import json
import time
import datetime
import sys
import statistics
from collections import defaultdict

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

print("="*115, flush=True)
print("📊 DETAILED AUDIT: SUB-$1.00 ORDERS, SHARE DEPTH ON BOTH SIDES & ABSORPTION SPEED", flush=True)
print("="*115, flush=True)

now_ts = int(time.time())
cur_w = (now_ts // 300) * 300

# Audit past 4 consecutive 5-minute candles (20 minutes of market data)
target_windows = [cur_w - (i * 300) for i in range(1, 5)]

all_opportunities = []

for w_s in target_windows:
    slug = f"btc-updown-5m-{w_s}"
    t_start = datetime.datetime.fromtimestamp(w_s, datetime.timezone.utc).strftime("%H:%M")
    t_end   = datetime.datetime.fromtimestamp(w_s + 300, datetime.timezone.utc).strftime("%H:%M UTC")
    
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
        if not r or not r[0].get("markets"): continue
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        
        # Fetch public trade history
        r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=1000", timeout=4).json()
        if not r_tr: continue
        
        trades = []
        for t in r_tr:
            tr_ts = t.get("timestamp") or t.get("matchTime")
            if isinstance(tr_ts, str):
                try: tr_ts = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00")).timestamp() if "T" in tr_ts else float(tr_ts)
                except: tr_ts = 0
            if tr_ts > 1e11: tr_ts /= 1000.0
            
            px = float(t.get("price", 0))
            side = str(t.get("side", "")).upper()
            outcome = str(t.get("outcome", "")).upper()
            sz = float(t.get("size", 0))
            if w_s <= tr_ts <= w_s + 300:
                trades.append({"ts": tr_ts, "sec": int(tr_ts - w_s), "side": side, "out": outcome, "px": px, "sz": sz})
                
        trades.sort(key=lambda x: x["ts"])
        
        # Group fills into temporal clusters (< 2.0s) where UP + DOWN < 0.98
        clusters = []
        for i, t1 in enumerate(trades):
            if t1["px"] < 0.05: continue
            for j in range(i+1, min(i+50, len(trades))):
                t2 = trades[j]
                if t2["px"] < 0.05: continue
                dt = t2["ts"] - t1["ts"]
                if dt > 3.0: break # Window up to 3 seconds
                
                # Opposite side check
                if (t1["out"] in ("UP", "YES") and t2["out"] in ("DOWN", "NO")) or (t1["out"] in ("DOWN", "NO") and t2["out"] in ("UP", "YES")):
                    comb_cost = t1["px"] + t2["px"]
                    if comb_cost <= 0.970: # Sub-$0.97 total
                        up_t = t1 if t1["out"] in ("UP", "YES") else t2
                        dn_t = t2 if t1["out"] in ("UP", "YES") else t1
                        
                        # Find how long liquidity lasted around these prices
                        up_like_trades = [t for t in trades if t["out"] in ("UP", "YES") and abs(t["px"] - up_t["px"]) <= 0.02 and abs(t["ts"] - up_t["ts"]) <= 10]
                        dn_like_trades = [t for t in trades if t["out"] in ("DOWN", "NO") and abs(t["px"] - dn_t["px"]) <= 0.02 and abs(t["ts"] - dn_t["ts"]) <= 10]
                        
                        up_duration = (max(t["ts"] for t in up_like_trades) - min(t["ts"] for t in up_like_trades)) if up_like_trades else 0.5
                        dn_duration = (max(t["ts"] for t in dn_like_trades) - min(t["ts"] for t in dn_like_trades)) if dn_like_trades else 0.5
                        
                        opp_window_duration = max(0.5, min(up_duration, dn_duration))
                        
                        all_opportunities.append({
                            "slug": slug,
                            "time_str": datetime.datetime.fromtimestamp(t1["ts"], datetime.timezone.utc).strftime("%H:%M:%S"),
                            "candle_sec": t1["sec"],
                            "time_diff_ms": int(dt * 1000),
                            "up_px": up_t["px"],
                            "up_sz": up_t["sz"],
                            "dn_px": dn_t["px"],
                            "dn_sz": dn_t["sz"],
                            "comb_cost": round(comb_cost, 3),
                            "profit_pct": round(((1.0 - comb_cost) / comb_cost) * 100.0, 1),
                            "dryup_sec": round(opp_window_duration, 2),
                            "dryup_ms": int(opp_window_duration * 1000)
                        })
    except Exception as e:
        continue

# Deduplicate similar overlapping events
deduped_opps = []
last_seen_sec = -100
for op in all_opportunities:
    if abs(op["candle_sec"] - last_seen_sec) >= 3:
        deduped_opps.append(op)
        last_seen_sec = op["candle_sec"]

print(f"Audited Recent Markets: Identified {len(deduped_opps)} distinct Sub-$0.97 Crossed Opportunities!\n")

print(f"{'Time (UTC)':<10} | {'UP Available':<18} | {'DOWN Available':<20} | {'Combined':<9} | {'Profit':<8} | {'Time Gap':<10} | {'Dry-Up Speed (Duration)'}")
print("-" * 115)

for op in deduped_opps[:20]:
    up_s = f"{op['up_sz']:.1f} sh @ ${op['up_px']:.2f}"
    dn_s = f"{op['dn_sz']:.1f} sh @ ${op['dn_px']:.2f}"
    gap_s = f"{op['time_diff_ms']} ms"
    dry_s = f"{op['dryup_sec']}s ({op['dryup_ms']} ms)"
    print(f"{op['time_str']:<10} | {up_s:<18} | {dn_s:<20} | ${op['comb_cost']:<8.3f} | +{op['profit_pct']:<6}% | {gap_s:<10} | {dry_s}")

print("-" * 115)

if deduped_opps:
    costs = [op["comb_cost"] for op in deduped_opps]
    profits = [op["profit_pct"] for op in deduped_opps]
    durations = [op["dryup_sec"] for op in deduped_opps]
    up_sizes = [op["up_sz"] for op in deduped_opps]
    dn_sizes = [op["dn_sz"] for op in deduped_opps]
    
    print(f"\n🎯 STATISTICAL BREAKDOWN FOR OPTIMAL ORDER PLACEMENT:")
    print(f"   • Average Combined Entry Cost:   ${statistics.mean(costs):.3f} (e.g. 78¢ + 16¢ = 94¢)")
    print(f"   • Average Guaranteed Net Profit:  +{statistics.mean(profits):.1f}%")
    print(f"   • Average UP Shares Available:    {statistics.mean(up_sizes):.1f} shares (Range: {min(up_sizes):.1f} to {max(up_sizes):.1f})")
    print(f"   • Average DOWN Shares Available:  {statistics.mean(dn_sizes):.1f} shares (Range: {min(dn_sizes):.1f} to {max(dn_sizes):.1f})")
    print(f"   • Average Time Before Dry-Up:     {statistics.mean(durations):.2f} seconds ({statistics.mean(durations)*1000:.0f} ms)")
    print(f"   • Median Time Before Dry-Up:      {statistics.median(durations):.2f} seconds ({statistics.median(durations)*1000:.0f} ms)")
    
    under_1s = sum(1 for d in durations if d <= 1.0)
    between_1_5s = sum(1 for d in durations if 1.0 < d <= 5.0)
    over_5s = sum(1 for d in durations if d > 5.0)
    
    print(f"\n   ⏱️ How Fast Liquidity Dries Up:")
    print(f"     • Fast Snipes (Lasted <= 1.0s):      {under_1s} events ({under_1s/len(durations)*100:.1f}%)")
    print(f"     • Standard Window (Lasted 1.0s - 5.0s): {between_1_5s} events ({between_1_5s/len(durations)*100:.1f}%)")
    print(f"     • Lingering Depth (Lasted > 5.0s):    {over_5s} events ({over_5s/len(durations)*100:.1f}%)")

print("="*115, flush=True)
