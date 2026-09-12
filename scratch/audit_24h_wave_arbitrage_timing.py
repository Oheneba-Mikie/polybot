import os
import sys
import json
import time
import datetime
import requests
import statistics
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

print("="*110, flush=True)
print("🔍 24-HOUR DUAL-LEG WAVE & SUB-$1.00 DISCREPANCY AUDIT (BTC 5-MIN MARKETS)", flush=True)
print("="*110, flush=True)

now = time.time()
cur_w_s = int(now // 300) * 300
all_windows = [cur_w_s - (i * 300) for i in range(288)]

def analyze_wave_arb(w_s):
    slug = f"btc-updown-5m-{w_s}"
    t_start_utc = datetime.datetime.fromtimestamp(w_s, datetime.timezone.utc)
    w_e = w_s + 300
    
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4.0)
        if r.status_code != 200: return None
        data = r.json()
        if not data or not data[0].get("markets"): return None
        
        mkt = data[0]["markets"][0]
        cid = mkt.get("conditionId")
        
        # Fetch trades
        r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=500", timeout=4.0)
        if r_tr.status_code != 200: return None
        trades = r_tr.json()
        if not trades or not isinstance(trades, list): return None
        
        up_buys = []
        dn_buys = []
        
        # Track all buy prices and their timestamps
        for t in trades:
            ts = t.get("timestamp") or t.get("matchTime")
            if isinstance(ts, str):
                try:
                    if "T" in ts:
                        ts = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                    else:
                        ts = float(ts)
                except:
                    ts = None
            if ts and ts > 1e11:
                ts = ts / 1000.0
                
            side = str(t.get("side", "")).upper()
            outcome = str(t.get("outcome", "")).upper()
            px = float(t.get("price", 0.0))
            sz = float(t.get("size", 0.0))
            
            # Filter valid trading window
            if ts and (w_s - 10 <= ts <= w_e + 10):
                if outcome in ("UP", "YES"):
                    up_buys.append({"ts": ts, "price": px, "size": sz, "side": side})
                elif outcome in ("DOWN", "NO"):
                    dn_buys.append({"ts": ts, "price": px, "size": sz, "side": side})
                    
        if not up_buys or not dn_buys:
            return None
            
        min_up_buy = min(t["price"] for t in up_buys if t["price"] > 0.05) if any(t["price"] > 0.05 for t in up_buys) else 1.0
        min_dn_buy = min(t["price"] for t in dn_buys if t["price"] > 0.05) if any(t["price"] > 0.05 for t in dn_buys) else 1.0
        
        combined_cost = min_up_buy + min_dn_buy
        has_wave_arb = combined_cost < 0.99
        profit_margin_pct = ((1.00 - combined_cost) / combined_cost) * 100.0 if has_wave_arb else 0.0
        
        # Calculate duration of the wave / time window between lowest UP and lowest DOWN
        up_low_trades = [t for t in up_buys if t["price"] <= min_up_buy + 0.03]
        dn_low_trades = [t for t in dn_buys if t["price"] <= min_dn_buy + 0.03]
        
        # Check time span when cheap shares were available
        up_low_duration_s = (max(t["ts"] for t in up_low_trades) - min(t["ts"] for t in up_low_trades)) if len(up_low_trades) > 1 else 1.0
        dn_low_duration_s = (max(t["ts"] for t in dn_low_trades) - min(t["ts"] for t in dn_low_trades)) if len(dn_low_trades) > 1 else 1.0
        
        return {
            "slug": slug,
            "time_utc": t_start_utc.strftime("%H:%M"),
            "trade_count": len(trades),
            "min_up": round(min_up_buy, 3),
            "min_dn": round(min_dn_buy, 3),
            "combined_cost": round(combined_cost, 3),
            "has_wave_arb": has_wave_arb,
            "profit_margin_pct": round(profit_margin_pct, 2),
            "up_window_duration_s": round(up_low_duration_s, 2),
            "dn_window_duration_s": round(dn_low_duration_s, 2),
            "avg_window_duration_s": round((up_low_duration_s + dn_low_duration_s) / 2.0, 2)
        }
    except Exception as e:
        return None

print(f"Auditing 288 windows for Dual-Leg Wave Arbitrage (25 threads)...", flush=True)
with ThreadPoolExecutor(max_workers=25) as executor:
    raw_results = list(executor.map(analyze_wave_arb, all_windows[::-1]))

valid_markets = [r for r in raw_results if r is not None]
arb_markets = [r for r in valid_markets if r["has_wave_arb"]]

print("\n" + "="*110, flush=True)
print(f"📊 24-HOUR DUAL-LEG WAVE ARBITRAGE REPORT ({len(valid_markets)} AUDITED 5M MARKETS)", flush=True)
print("="*110, flush=True)

print(f"\n1. 🎯 OCCURRENCE FREQUENCY:")
print(f"   • Total Active 5m Markets Audited: {len(valid_markets)}")
print(f"   • Markets where Dual-Leg Combined Cost was < $0.99 (Guaranteed Win): {len(arb_markets)} ({len(arb_markets)/max(1, len(valid_markets))*100:.1f}%)")

if arb_markets:
    comb_costs = [r["combined_cost"] for r in arb_markets]
    profits = [r["profit_margin_pct"] for r in arb_markets]
    durations = [r["avg_window_duration_s"] for r in arb_markets]
    
    print(f"   • Average Combined Cost (UP + DOWN): ${statistics.mean(comb_costs):.3f}")
    print(f"   • Best Combined Cost Found:          ${min(comb_costs):.3f} (Profit: +{((1.0 - min(comb_costs))/min(comb_costs)*100):.1f}%)")
    print(f"   • Average Guaranteed Net Profit:     +{statistics.mean(profits):.2f}%")
    
    print(f"\n2. ⏱️ HOW LONG DISCREPANCY WINDOWS STAY OPEN (Duration of Mispricing):")
    print(f"   • Average Time Cheap Shares Sat on the Book: {statistics.mean(durations):.2f} seconds ({statistics.mean(durations)*1000:.0f} ms)")
    print(f"   • Median Time Window:                        {statistics.median(durations):.2f} seconds ({statistics.median(durations)*1000:.0f} ms)")
    
    gt_700ms = sum(1 for d in durations if d >= 0.70)
    gt_2s    = sum(1 for d in durations if d >= 2.0)
    gt_10s   = sum(1 for d in durations if d >= 10.0)
    lt_700ms = sum(1 for d in durations if d < 0.70)
    
    print(f"\n   📈 Duration Breakdown:")
    print(f"     • Windows lasting > 700 ms:    {gt_700ms} markets ({gt_700ms/len(arb_markets)*100:.1f}%)")
    print(f"     • Windows lasting > 2.0s:      {gt_2s} markets ({gt_2s/len(arb_markets)*100:.1f}%)")
    print(f"     • Windows lasting > 10.0s:     {gt_10s} markets ({gt_10s/len(arb_markets)*100:.1f}%)")
    print(f"     • Instant Sub-700ms Snipes:    {lt_700ms} markets ({lt_700ms/len(arb_markets)*100:.1f}%)")

print("\n3. 📋 SAMPLE OF RECENT 24H WAVE ARBITRAGE ROUNDS:")
print(f"{'Time (UTC)':<10} | {'Slug':<26} | {'Min UP':<8} | {'Min DOWN':<9} | {'Total Cost':<11} | {'Profit %':<9} | {'Duration'}")
print("-" * 100)
for m in arb_markets[-20:]:
    print(f"{m['time_utc']:<10} | {m['slug']:<26} | ${m['min_up']:<7.3f} | ${m['min_dn']:<8.3f} | ${m['combined_cost']:<10.3f} | +{m['profit_margin_pct']:<7.2f}% | {m['avg_window_duration_s']:.1f}s ({m['avg_window_duration_s']*1000:.0f}ms)")

print("="*110, flush=True)

# Save json
with open("scratch/dual_leg_wave_arbitrage_24h.json", "w", encoding="utf-8") as f:
    json.dump({"valid_markets": len(valid_markets), "arb_markets": arb_markets}, f, indent=2)
