import requests
import json
import time
import datetime
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# Check the last 2 completed 5m markets (7:10 PM - 7:15 PM ET and 7:15 PM - 7:20 PM ET)
now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - 600, cur_w - 300] # 1789254600 and 1789254900

print("="*120, flush=True)
print("📊 EXACT TIMESTAMP AUDIT: SUB-$1.00 COMBINATIONS, REAL BUYER FILLS & SHARE AVAILABILITY", flush=True)
print("="*120, flush=True)

for w_s in windows:
    slug = f"btc-updown-5m-{w_s}"
    t_start_et = datetime.datetime.fromtimestamp(w_s - 4*3600, datetime.timezone.utc).strftime("%I:%M %p ET")
    t_end_et   = datetime.datetime.fromtimestamp(w_s + 300 - 4*3600, datetime.timezone.utc).strftime("%I:%M %p ET")
    
    print(f"\n📌 MARKET: {slug} ({t_start_et} -> {t_end_et})", flush=True)
    print("-" * 120, flush=True)
    
    r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
    if not r_evt or not r_evt[0].get("markets"): continue
    mkt = r_evt[0]["markets"][0]
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
    print(f"Total Fills in Candle: {len(trades)} trades | UP Trades: {len([t for t in trades if t['out'] in ('UP','YES')])} | DOWN Trades: {len([t for t in trades if t['out'] in ('DOWN','NO')])}\n")
    
    # Track pairings where UP + DOWN < 1.00
    print(f"{'Exact Time (UTC)':<18} | {'Leg 1: How Person Bought':<30} | {'Leg 2: How Person Bought':<30} | {'Combined (<$1.00)':<18} | {'Profit'}")
    print("-" * 120)
    
    shown = 0
    for i, t1 in enumerate(trades):
        if t1["px"] < 0.05 or t1["px"] > 0.95: continue
        for j in range(i+1, len(trades)):
            t2 = trades[j]
            if t2["px"] < 0.05 or t2["px"] > 0.95: continue
            
            # Check if opposite outcome
            if (t1["out"] in ("UP", "YES") and t2["out"] in ("DOWN", "NO")) or (t1["out"] in ("DOWN", "NO") and t2["out"] in ("UP", "YES")):
                comb = t1["px"] + t2["px"]
                if comb < 0.980:
                    dt = t2["ts"] - t1["ts"]
                    t1_str = datetime.datetime.fromtimestamp(t1["ts"], datetime.timezone.utc).strftime("%H:%M:%S")
                    t2_str = datetime.datetime.fromtimestamp(t2["ts"], datetime.timezone.utc).strftime("%H:%M:%S")
                    
                    l1 = f"{t1['side']} {t1['sz']:.1f} sh {t1['out']} @ ${t1['px']:.2f}"
                    l2 = f"{t2['side']} {t2['sz']:.1f} sh {t2['out']} @ ${t2['px']:.2f}"
                    comb_s = f"${comb:.3f} (Δ {dt:.1f}s)"
                    prof_s = f"+{((1.0-comb)/comb)*100:.1f}%"
                    
                    print(f"[{t1_str} -> {t2_str}]  | {l1:<30} | {l2:<30} | {comb_s:<18} | {prof_s}")
                    shown += 1
                    if shown >= 15: break
        if shown >= 15: break

print("="*120, flush=True)
