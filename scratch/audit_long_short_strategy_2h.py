import requests
import json
import time
import datetime
import sys
import statistics

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

print("="*110, flush=True)
print("📊 2-HOUR EMPIRICAL AUDIT: THE 'LONG SHORT STRATEGY' (BTC 5-MIN MARKETS)", flush=True)
print("="*110, flush=True)

now_ts = int(time.time())
cur_w_s = (now_ts // 300) * 300

# 24 consecutive 5-minute candles in the past 2 hours
windows = [cur_w_s - (i * 300) for i in range(1, 25)]

results = []

print(f"Auditing all 24 consecutive 5m candles from {datetime.datetime.fromtimestamp(windows[-1], datetime.timezone.utc).strftime('%H:%M UTC')} to {datetime.datetime.fromtimestamp(windows[0], datetime.timezone.utc).strftime('%H:%M UTC')}...\n", flush=True)

for ts in windows[::-1]: # Chronological order
    slug = f"btc-updown-5m-{ts}"
    t_start_utc = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M")
    
    try:
        r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r_evt or not r_evt[0].get("markets"): continue
        mkt = r_evt[0]["markets"][0]
        cid = mkt.get("conditionId")
        outcome_prices = json.loads(mkt.get("outcomePrices", "[]")) if mkt.get("outcomePrices") else []
        
        up_final = float(outcome_prices[0]) if len(outcome_prices) > 0 else None
        dn_final = float(outcome_prices[1]) if len(outcome_prices) > 1 else None
        
        if up_final is None or dn_final is None: continue
        actual_winner = "UP" if up_final >= 0.9 else ("DOWN" if dn_final >= 0.9 else "UNDETERMINED")
        
        # Fetch trades
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
            if ts <= tr_ts <= ts + 300:
                trades.append({"ts": tr_ts, "sec": int(tr_ts - ts), "side": side, "out": outcome, "px": px, "sz": sz})
                
        trades.sort(key=lambda x: x["ts"])
        if len(trades) < 5: continue
        
        # SIMULATE THE "LONG SHORT STRATEGY":
        # 1. Step 1: Detect early winning momentum (first side that crosses $0.60-$0.70 during first 2 mins)
        leg1_trade = None
        leg1_side = None
        leg1_price = None
        
        for t in trades:
            if t["sec"] <= 150: # First 2.5 minutes
                if t["px"] >= 0.60 and t["px"] <= 0.75:
                    leg1_trade = t
                    leg1_side = t["out"]
                    leg1_price = t["px"]
                    break
                    
        # If no momentum trade, take early leading trade near 55c
        if not leg1_trade:
            for t in trades:
                if t["sec"] <= 90 and 0.50 <= t["px"] <= 0.60:
                    leg1_trade = t
                    leg1_side = t["out"]
                    leg1_price = t["px"]
                    break
                    
        if not leg1_trade: continue
        
        # 2. Step 2: Watch the losing side (opposite outcome) when wave drops it to cheap levels
        opp_side = "DOWN" if leg1_side in ("UP", "YES") else "UP"
        
        # Look for trades on opposite side AFTER leg1 entry
        opp_trades_after = [t for t in trades if t["ts"] >= leg1_trade["ts"] and t["out"] == opp_side and t["px"] <= 0.25]
        
        leg2_price = None
        leg2_sec = None
        if opp_trades_after:
            # Pick lowest available fill on opposite side during the wave
            best_opp = min(opp_trades_after, key=lambda x: x["px"])
            leg2_price = best_opp["px"]
            leg2_sec = best_opp["sec"]
            
        combined_cost = (leg1_price + leg2_price) if leg2_price is not None else None
        
        is_hedged_win = (combined_cost is not None and combined_cost < 1.00)
        unhedged_win = (leg2_price is None and leg1_side == actual_winner)
        unhedged_loss = (leg2_price is None and leg1_side != actual_winner)
        over_1_loss = (combined_cost is not None and combined_cost >= 1.00)
        
        pnl = 0.0
        pnl_pct = 0.0
        status_str = ""
        
        if is_hedged_win:
            pnl_pct = ((1.00 - combined_cost) / combined_cost) * 100.0
            pnl = (1.00 - combined_cost) * 10.0 # On $10 stake
            status_str = f"HEDGED WIN (+{pnl_pct:.1f}%)"
        elif unhedged_win:
            pnl_pct = ((1.00 - leg1_price) / leg1_price) * 100.0
            pnl = (1.00 - leg1_price) * 10.0
            status_str = f"NAKED WIN (+{pnl_pct:.1f}%)"
        elif over_1_loss:
            pnl_pct = ((1.00 - combined_cost) / combined_cost) * 100.0
            pnl = (1.00 - combined_cost) * 10.0
            status_str = f"OVER-$1 LOSS ({pnl_pct:.1f}%)"
        else:
            pnl_pct = -100.0
            pnl = -10.0
            status_str = "LEG-1 LOSS (-100%)"
            
        results.append({
            "slug": slug,
            "time_utc": t_start_utc,
            "winner": actual_winner,
            "leg1_side": leg1_side,
            "leg1_px": leg1_price,
            "leg1_sec": leg1_trade["sec"],
            "leg2_px": leg2_price,
            "leg2_sec": leg2_sec,
            "combined": combined_cost,
            "status": status_str,
            "is_win": pnl > 0,
            "pnl": pnl,
            "pnl_pct": pnl_pct
        })
    except Exception as e:
        continue

print(f"{'Time (UTC)':<10} | {'Winner':<7} | {'Leg 1 (Winning)':<18} | {'Leg 2 (Losing Wave)':<20} | {'Total Cost':<11} | {'Outcome Status':<22} | {'P&L ($10)'}")
print("-" * 110)

total_pnl = 0.0
wins = 0
losses = 0

for r in results:
    l1_str = f"{r['leg1_side']} @ ${r['leg1_px']:.2f} (T+{r['leg1_sec']}s)"
    l2_str = f"{'DOWN' if r['leg1_side']=='UP' else 'UP'} @ ${r['leg2_px']:.2f} (T+{r['leg2_sec']}s)" if r['leg2_px'] is not None else "No Cheap Wave"
    comb_str = f"${r['combined']:.3f}" if r['combined'] is not None else f"${r['leg1_px']:.2f} (Naked)"
    pnl_str = f"+${r['pnl']:.2f}" if r['pnl'] >= 0 else f"-${abs(r['pnl']):.2f}"
    
    total_pnl += r["pnl"]
    if r["is_win"]: wins += 1
    else: losses += 1
    
    print(f"{r['time_utc']:<10} | {r['winner']:<7} | {l1_str:<18} | {l2_str:<20} | {comb_str:<11} | {r['status']:<22} | {pnl_str}")

print("-" * 110)
print(f"🎯 2-HOUR SUMMARY FOR THE LONG SHORT STRATEGY:")
print(f"   • Total 5m Candles Audited: {len(results)}")
print(f"   • Winning Rounds:           {wins} ({wins/max(1, len(results))*100:.1f}%)")
print(f"   • Losing Rounds:            {losses} ({losses/max(1, len(results))*100:.1f}%)")
print(f"   • Net Cumulative Profit:    {'+' if total_pnl>=0 else ''}${total_pnl:.2f} (Starting with $10 stake)")
if wins > 0:
    hedged_rounds = [r for r in results if r["combined"] is not None and r["combined"] < 1.0]
    print(f"   • Successfully Hedged Sub-$1.00 Pairs: {len(hedged_rounds)} / {len(results)} ({len(hedged_rounds)/len(results)*100:.1f}%)")
    if hedged_rounds:
        avg_cost = statistics.mean(r["combined"] for r in hedged_rounds)
        print(f"   • Average Pair Cost when Hedged:       ${avg_cost:.3f} (Net +{((1.0-avg_cost)/avg_cost)*100:.1f}% Return)")
print("="*110, flush=True)
