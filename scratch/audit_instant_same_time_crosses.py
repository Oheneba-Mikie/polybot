import requests
import json
import time
import datetime
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

DATA_HOST = 'https://data-api.polymarket.com'
GAMMA_HOST = 'https://gamma-api.polymarket.com'

# Check recent markets for exact same-second crosses (Time Difference <= 1.0s)
now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - 900, cur_w - 600, cur_w - 300, 1789213800]

print("="*145, flush=True)
print("🎯 INSTANT SAME-SECOND CROSS ARBITRAGE (SAME MILLISECOND EXECUTION)", flush=True)
print("="*145, flush=True)

same_sec_opps = []

for w_s in windows:
    slug = f"btc-updown-5m-{w_s}"
    try:
        r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r_evt or not r_evt[0].get("markets"): continue
        cid = r_evt[0]["markets"][0].get("conditionId")
        trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=1000", timeout=4).json()
        if not trades: continue
    except Exception:
        continue
        
    parsed = []
    for t in trades:
        tr_ts = t.get("timestamp") or t.get("matchTime")
        if isinstance(tr_ts, str):
            try: tr_ts = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00")).timestamp() if "T" in tr_ts else float(tr_ts)
            except: tr_ts = 0
        if tr_ts > 1e11: tr_ts /= 1000.0
        parsed.append({
            "ts": tr_ts,
            "price": float(t.get("price", 0)),
            "size": float(t.get("size", 0)),
            "outcome": str(t.get("outcome", "")).upper()
        })
    parsed.sort(key=lambda x: x["ts"])
    
    for i, t1 in enumerate(parsed):
        for j in range(i+1, min(i+25, len(parsed))):
            t2 = parsed[j]
            dt = t2["ts"] - t1["ts"]
            if dt > 1.2: break # Only exact same second / < 1.2s
            
            if (t1["outcome"] in ("UP","YES") and t2["outcome"] in ("DOWN","NO")) or (t1["outcome"] in ("DOWN","NO") and t2["outcome"] in ("UP","YES")):
                comb = round(t1["price"] + t2["price"], 3)
                if comb <= 0.980:
                    up_t = t1 if t1["outcome"] in ("UP","YES") else t2
                    dn_t = t2 if t1["outcome"] in ("UP","YES") else t1
                    
                    # Compute available shares around this exact tick
                    up_cluster = sum(t["size"] for t in parsed if t["outcome"] in ("UP","YES") and abs(t["price"] - up_t["price"]) <= 0.01 and abs(t["ts"] - up_t["ts"]) <= 3.0)
                    dn_cluster = sum(t["size"] for t in parsed if t["outcome"] in ("DOWN","NO") and abs(t["price"] - dn_t["price"]) <= 0.01 and abs(t["ts"] - dn_t["ts"]) <= 3.0)
                    
                    # Calculate how many seconds before this price level completely dried up
                    subsequent = [t for t in parsed[j+1:] if t["ts"] - t1["ts"] <= 10.0]
                    dry_up_time = dt
                    for sub in subsequent:
                        if (sub["outcome"] == up_t["outcome"] and abs(sub["price"] - up_t["price"]) <= 0.01) or (sub["outcome"] == dn_t["outcome"] and abs(sub["price"] - dn_t["price"]) <= 0.01):
                            dry_up_time = max(dry_up_time, sub["ts"] - t1["ts"])
                            
                    t1_str = datetime.datetime.fromtimestamp(t1["ts"], datetime.timezone.utc).strftime("%H:%M:%S")
                    
                    same_sec_opps.append({
                        "ts_utc": t1_str,
                        "time_gap": f"{int(dt*1000)}ms" if dt < 1.0 else f"{round(dt,1)}s",
                        "up_px": up_t["price"],
                        "up_sz": max(up_t["size"], round(up_cluster, 1)),
                        "up_fill": up_t["size"],
                        "dn_px": dn_t["price"],
                        "dn_sz": max(dn_t["size"], round(dn_cluster, 1)),
                        "dn_fill": dn_t["size"],
                        "comb": comb,
                        "profit_usd": round(1.0 - comb, 3),
                        "profit_pct": round(((1.0 - comb)/comb)*100, 1),
                        "dry_up": f"Dried up in {round(dry_up_time, 1)}s" if dry_up_time >= 1.0 else f"Dried up in {int(dry_up_time*1000)}ms"
                    })

# Deduplicate
deduped = []
seen = set()
for s in same_sec_opps:
    k = (s["ts_utc"], s["up_px"], s["dn_px"])
    if k not in seen:
        deduped.append(s)
        seen.add(k)

header = f"{'Exact Timestamp (UTC)':<22} | {'UP Available & Price':<24} | {'DOWN Available & Price':<24} | {'Total Cost':<10} | {'Execution Gap':<14} | {'How Soon It Dried Up':<22} | {'Guaranteed Profit'}"
print(header, flush=True)
print("-" * len(header), flush=True)

for d in deduped[:25]:
    up_s = f"{d['up_sz']:>5.1f} sh (Bt {d['up_fill']:.1f}) @ ${d['up_px']:.2f}"
    dn_s = f"{d['dn_sz']:>5.1f} sh (Bt {d['dn_fill']:.1f}) @ ${d['dn_px']:.2f}"
    cost_s = f"${d['comb']:.3f} ({int(round(d['comb']*100))}¢)"
    gap_s = f"{d['time_gap']} (Instant)"
    prof_s = f"+${d['profit_usd']:.3f} (+{d['profit_pct']}%)"
    print(f"{d['ts_utc']:<22} | {up_s:<24} | {dn_s:<24} | {cost_s:<10} | {gap_s:<14} | {d['dry_up']:<22} | {prof_s}", flush=True)

print("="*145, flush=True)
