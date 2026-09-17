import requests
import json
import time
import datetime
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - 600, cur_w - 300, cur_w]

print("="*145, flush=True)
print("📊 LIVE & RECENT AUDIT: DUAL-LEG DEPTH, SUB-$1.00 TRANSACTIONS & EXACT DRY-UP DURATION", flush=True)
print("="*145, flush=True)

results = []

for w_s in windows:
    slug = f"btc-updown-5m-{w_s}"
    t_start_et = datetime.datetime.fromtimestamp(w_s - 4*3600, datetime.timezone.utc).strftime("%I:%M %p ET")
    t_end_et   = datetime.datetime.fromtimestamp(w_s + 300 - 4*3600, datetime.timezone.utc).strftime("%I:%M %p ET")
    
    try:
        r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r_evt or not r_evt[0].get("markets"): continue
        mkt = r_evt[0]["markets"][0]
        cid = mkt.get("conditionId")
        
        r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=1000", timeout=4).json()
        if not r_tr: continue
    except Exception:
        continue
    
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
    
    for i, t1 in enumerate(trades):
        if t1["px"] < 0.05 or t1["px"] > 0.95: continue
        for j in range(i+1, min(i+50, len(trades))):
            t2 = trades[j]
            if t2["px"] < 0.05 or t2["px"] > 0.95: continue
            
            # Opposite outcome check
            if (t1["out"] in ("UP", "YES") and t2["out"] in ("DOWN", "NO")) or (t1["out"] in ("DOWN", "NO") and t2["out"] in ("UP", "YES")):
                comb = t1["px"] + t2["px"]
                if comb <= 0.970:
                    dt = t2["ts"] - t1["ts"]
                    if dt <= 35.0:
                        up_t = t1 if t1["out"] in ("UP", "YES") else t2
                        dn_t = t2 if t1["out"] in ("UP", "YES") else t1
                        
                        # Cluster volume & time window before drying up
                        up_trades_in_cluster = [t for t in trades if t["out"] in ("UP", "YES") and abs(t["px"] - up_t["px"]) <= 0.02 and abs(t["ts"] - up_t["ts"]) <= 10.0]
                        dn_trades_in_cluster = [t for t in trades if t["out"] in ("DOWN", "NO") and abs(t["px"] - dn_t["px"]) <= 0.02 and abs(t["ts"] - dn_t["ts"]) <= 10.0]
                        
                        up_cluster_vol = sum(t["sz"] for t in up_trades_in_cluster)
                        dn_cluster_vol = sum(t["sz"] for t in dn_trades_in_cluster)
                        
                        # Calculate dry-up duration
                        up_span = max(0.5, round(max(t["ts"] for t in up_trades_in_cluster) - min(t["ts"] for t in up_trades_in_cluster), 1)) if up_trades_in_cluster else 0.5
                        dn_span = max(0.5, round(max(t["ts"] for t in dn_trades_in_cluster) - min(t["ts"] for t in dn_trades_in_cluster), 1)) if dn_trades_in_cluster else 0.5
                        
                        t1_str = datetime.datetime.fromtimestamp(t1["ts"], datetime.timezone.utc).strftime("%H:%M:%S")
                        t2_str = datetime.datetime.fromtimestamp(t2["ts"], datetime.timezone.utc).strftime("%H:%M:%S")
                        
                        results.append({
                            "market": f"{t_start_et} ET",
                            "time_range": f"[{t1_str} -> {t2_str}]",
                            "up_px": up_t["px"],
                            "up_fill": up_t["sz"],
                            "up_avail": max(up_t["sz"], round(up_cluster_vol, 1)),
                            "up_dryup": f"Dried up in {up_span}s" if up_span > 0.5 else "Dried up in <1s",
                            "dn_px": dn_t["px"],
                            "dn_fill": dn_t["sz"],
                            "dn_avail": max(dn_t["sz"], round(dn_cluster_vol, 1)),
                            "dn_dryup": f"Dried up in {dn_span}s" if dn_span > 0.5 else "Dried up in <1s",
                            "comb_cost": round(comb, 3),
                            "dt_sec": round(dt, 1),
                            "profit_pct": round(((1.0 - comb) / comb) * 100.0, 1),
                            "profit_usd": round(1.0 - comb, 3)
                        })

# Deduplicate
deduped = []
seen = set()
for r in results:
    key = (r["market"], r["time_range"], r["comb_cost"])
    if key not in seen:
        deduped.append(r)
        seen.add(key)

print(f"{'Exact Timestamps (UTC)':<22} | {'UP Shares & Price':<24} | {'UP Dry-Up':<16} | {'DOWN Shares & Price':<24} | {'DOWN Dry-Up':<16} | {'Total Cost':<10} | {'Time Gap':<9} | {'Guaranteed Profit'}")
print("-" * 145)

for d in deduped[:25]:
    up_str = f"{d['up_avail']:>5.1f} sh (Bt {d['up_fill']:.1f}) @ ${d['up_px']:.2f}"
    dn_str = f"{d['dn_avail']:>5.1f} sh (Bt {d['dn_fill']:.1f}) @ ${d['dn_px']:.2f}"
    cost_str = f"${d['comb_cost']:.3f} ({int(round(d['comb_cost']*100))}¢)"
    gap_str = f"{d['dt_sec']}s"
    prof_str = f"+${d['profit_usd']:.3f} (+{d['profit_pct']}%)"
    print(f"{d['time_range']:<22} | {up_str:<24} | {d['up_dryup']:<16} | {dn_str:<24} | {d['dn_dryup']:<16} | {cost_str:<10} | {gap_str:<9} | {prof_str}")

print("="*145, flush=True)
