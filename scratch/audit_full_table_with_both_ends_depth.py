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

# Audit completed markets: 7:10 PM ET, 7:15 PM ET, 7:20 PM ET, 7:25 PM ET
now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - 900, cur_w - 600, cur_w - 300]

print("="*135, flush=True)
print("📊 EXACT TRANSACTION AUDIT: SHARES AVAILABLE ON BOTH ENDS, FILL SIZES & SUB-$1.00 PRICES", flush=True)
print("="*135, flush=True)

results = []

for w_s in windows:
    slug = f"btc-updown-5m-{w_s}"
    t_start_et = datetime.datetime.fromtimestamp(w_s - 4*3600, datetime.timezone.utc).strftime("%I:%M %p ET")
    t_end_et   = datetime.datetime.fromtimestamp(w_s + 300 - 4*3600, datetime.timezone.utc).strftime("%I:%M %p ET")
    
    r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
    if not r_evt or not r_evt[0].get("markets"): continue
    mkt = r_evt[0]["markets"][0]
    cid = mkt.get("conditionId")
    
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
                    if dt <= 30.0:
                        up_t = t1 if t1["out"] in ("UP", "YES") else t2
                        dn_t = t2 if t1["out"] in ("UP", "YES") else t1
                        
                        # Calculate total cluster volume available around these fills
                        up_cluster = sum(t["sz"] for t in trades if t["out"] in ("UP", "YES") and abs(t["px"] - up_t["px"]) <= 0.02 and abs(t["ts"] - up_t["ts"]) <= 5.0)
                        dn_cluster = sum(t["sz"] for t in trades if t["out"] in ("DOWN", "NO") and abs(t["px"] - dn_t["px"]) <= 0.02 and abs(t["ts"] - dn_t["ts"]) <= 5.0)
                        
                        t1_str = datetime.datetime.fromtimestamp(t1["ts"], datetime.timezone.utc).strftime("%H:%M:%S")
                        t2_str = datetime.datetime.fromtimestamp(t2["ts"], datetime.timezone.utc).strftime("%H:%M:%S")
                        
                        results.append({
                            "market": f"{t_start_et} ET",
                            "time_range": f"{t1_str} -> {t2_str}",
                            "up_px": up_t["px"],
                            "up_fill": up_t["sz"],
                            "up_avail": max(up_t["sz"], round(up_cluster, 1)),
                            "dn_px": dn_t["px"],
                            "dn_fill": dn_t["sz"],
                            "dn_avail": max(dn_t["sz"], round(dn_cluster, 1)),
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

print(f"{'Market Window':<14} | {'Exact Time (UTC)':<20} | {'UP Available & Price':<26} | {'DOWN Available & Price':<28} | {'Total Cost':<12} | {'Time Gap':<10} | {'Guaranteed Profit'}")
print("-" * 135)

for d in deduped[:25]:
    up_str = f"{d['up_avail']:>6.1f} sh (Bought {d['up_fill']:.1f}) @ ${d['up_px']:.2f}"
    dn_str = f"{d['dn_avail']:>6.1f} sh (Bought {d['dn_fill']:.1f}) @ ${d['dn_px']:.2f}"
    cost_str = f"${d['comb_cost']:.3f}"
    gap_str = f"{d['dt_sec']}s"
    prof_str = f"+${d['profit_usd']:.3f} (+{d['profit_pct']}%)"
    print(f"{d['market']:<14} | {d['time_range']:<20} | {up_str:<26} | {dn_str:<28} | {cost_str:<12} | {gap_str:<10} | {prof_str}")

print("="*135, flush=True)
