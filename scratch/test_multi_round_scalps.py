import os
import sys
import json
import time
import datetime
import requests
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST = "https://data-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"

print("="*100)
print("🔍 RESEARCH: HOW MANY TIMES CAN WE BUY -> SELL -> RE-BUY -> RE-SELL IN A SINGLE 5-MIN CANDLE?")
print("="*100)

now = time.time()
current_w_s = int(now // 300) * 300
num_candles = 24 # 2 hours
candle_timestamps = [current_w_s - (i * 300) for i in range(num_candles)]
candle_timestamps.reverse()

multi_cycle_results = []

for ts in candle_timestamps:
    slug = f"btc-updown-5m-{ts}"
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M UTC")
    
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
        if not r or not r[0].get("markets"):
            continue
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        title = mkt.get("question", slug)
        
        r_t = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=500", timeout=5).json()
        trades = r_t if r_t else []
        if not trades:
            continue
            
        sorted_trades = sorted(trades, key=lambda x: x.get("timestamp", 0))
        
        # Analyze cycles of Buy @ <=0.97 -> Sell @ >=0.98 within this single candle
        up_trades = [(t.get("timestamp", 0), float(t.get("price", 0)), float(t.get("size", 0))) for t in trades if str(t.get("outcome")).lower() in ("up", "yes")]
        dn_trades = [(t.get("timestamp", 0), float(t.get("price", 0)), float(t.get("size", 0))) for t in trades if str(t.get("outcome")).lower() in ("down", "no")]
        
        # Check both UP and DOWN for multiple scalp cycles
        for side_name, side_trades in [("UP", up_trades), ("DOWN", dn_trades)]:
            cycles = []
            in_position = False
            entry_t = None
            entry_p = None
            
            for t_idx, (t_sec, px, sz) in enumerate(side_trades):
                if not in_position:
                    # Buy trigger: price is <= 0.97
                    if 0.95 <= px <= 0.975:
                        in_position = True
                        entry_t = t_sec
                        entry_p = px
                else:
                    # Sell trigger: price reaches >= 0.98
                    if px >= 0.98:
                        hold_time = t_sec - entry_t
                        cycles.append({
                            "entry_t": entry_t,
                            "exit_t": t_sec,
                            "entry_px": entry_p,
                            "exit_px": px,
                            "hold_sec": hold_time,
                            "profit_pct": ((px - entry_p) / entry_p) * 100.0
                        })
                        in_position = False # Exited! Ready to re-buy!
            
            if len(cycles) > 0:
                multi_cycle_results.append({
                    "candle": dt_str,
                    "slug": slug,
                    "side": side_name,
                    "total_cycles": len(cycles),
                    "cycles": cycles
                })

    except Exception as e:
        continue

print(f"Audited {len(candle_timestamps)} candles across past 2 hours.")
print(f"Found {len(multi_cycle_results)} candle sides with scalp opportunities.\n")

print("="*100)
print(f"{'CANDLE (UTC)':<14} | {'SIDE':<5} | {'CYCLES (BUY->SELL ROUNDTRIPS)':<30} | {'DETAILS OF EACH CYCLE (ENTRY -> EXIT)'}")
print("="*100)

total_cycles_count = defaultdict(int)

for r in multi_cycle_results:
    cycles = r["cycles"]
    num_c = len(cycles)
    total_cycles_count[num_c] += 1
    
    cycle_summary = " | ".join([f"#{i+1}: {c['entry_px']:.2f}→{c['exit_px']:.2f} ({c['hold_sec']}s)" for i, c in enumerate(cycles)])
    print(f"{r['candle']:<14} | {r['side']:<5} | {num_c} roundtrips in 5 mins          | {cycle_summary[:60]}")

print("\n" + "="*100)
print("📊 DISTRIBUTION: HOW MANY TIMES CAN YOU BUY & SELL IN 1 SINGLE CANDLE?")
print("="*100)
for count, occurrences in sorted(total_cycles_count.items()):
    print(f"• {count} Roundtrip(s) per candle: Occurred in {occurrences} candle markets")

print("="*100)
