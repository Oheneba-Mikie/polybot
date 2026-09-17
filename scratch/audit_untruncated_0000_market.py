import requests
import json
import time
import datetime
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

DATA_HOST = 'https://data-api.polymarket.com'
GAMMA_HOST = 'https://gamma-api.polymarket.com'

# Window 00:00:00 UTC to 00:05:00 UTC (1789257600)
w_s = 1789257600
slug = f"btc-updown-5m-{w_s}"

try:
    r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
    if not r_evt or not r_evt[0].get("markets"):
        print(f"Could not find {slug}")
        sys.exit(1)
    mkt = r_evt[0]["markets"][0]
    cid = mkt.get("conditionId")
    trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=2000", timeout=5).json()
except Exception as e:
    print(f"Error fetching: {e}")
    sys.exit(1)

parsed = []
for t in trades:
    tr_ts = t.get("timestamp") or t.get("matchTime")
    if isinstance(tr_ts, str):
        try: tr_ts = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00")).timestamp() if "T" in tr_ts else float(tr_ts)
        except: tr_ts = 0
    if tr_ts > 1e11: tr_ts /= 1000.0
    if w_s <= tr_ts <= w_s + 300:
        parsed.append({
            "ts": tr_ts,
            "sec": int(tr_ts - w_s),
            "countdown": 300 - int(tr_ts - w_s),
            "price": float(t.get("price", 0)),
            "size": float(t.get("size", 0)),
            "outcome": str(t.get("outcome", "")).upper()
        })
parsed.sort(key=lambda x: x["ts"])

t_start_utc = datetime.datetime.fromtimestamp(w_s, datetime.timezone.utc).strftime("%H:%M:%S UTC")
t_end_utc   = datetime.datetime.fromtimestamp(w_s + 300, datetime.timezone.utc).strftime("%H:%M:%S UTC")

print("="*150, flush=True)
print(f"📊 EXHAUSTIVE UNTRUNCATED AUDIT: {slug} ({t_start_utc} to {t_end_utc})", flush=True)
print(f"Total Trades in 5-Minute Window: {len(parsed)}", flush=True)
print("="*150, flush=True)

# Find ALL instant same-second crossed opportunities (dt <= 1.2s, combined <= 0.985)
opps = []
for i, t1 in enumerate(parsed):
    for j in range(i+1, min(i+40, len(parsed))):
        t2 = parsed[j]
        dt = t2["ts"] - t1["ts"]
        if dt > 1.2: break
        
        if (t1["outcome"] in ("UP","YES") and t2["outcome"] in ("DOWN","NO")) or (t1["outcome"] in ("DOWN","NO") and t2["outcome"] in ("UP","YES")):
            comb = round(t1["price"] + t2["price"], 3)
            if comb <= 0.985:
                up_t = t1 if t1["outcome"] in ("UP","YES") else t2
                dn_t = t2 if t1["outcome"] in ("UP","YES") else t1
                
                # Available cluster volume
                up_vol = sum(t["size"] for t in parsed if t["outcome"] in ("UP","YES") and abs(t["price"] - up_t["price"]) <= 0.01 and abs(t["ts"] - up_t["ts"]) <= 3.0)
                dn_vol = sum(t["size"] for t in parsed if t["outcome"] in ("DOWN","NO") and abs(t["price"] - dn_t["price"]) <= 0.01 and abs(t["ts"] - dn_t["ts"]) <= 3.0)
                
                # Dry up time
                subsequent = [t for t in parsed[j+1:] if t["ts"] - t1["ts"] <= 20.0]
                dry_up = dt
                for sub in subsequent:
                    if (sub["outcome"] == up_t["outcome"] and abs(sub["price"] - up_t["price"]) <= 0.01) or (sub["outcome"] == dn_t["outcome"] and abs(sub["price"] - dn_t["price"]) <= 0.01):
                        dry_up = max(dry_up, sub["ts"] - t1["ts"])
                        
                t1_str = datetime.datetime.fromtimestamp(t1["ts"], datetime.timezone.utc).strftime("%H:%M:%S")
                
                opps.append({
                    "sec": t1["sec"],
                    "countdown": t1["countdown"],
                    "time_utc": t1_str,
                    "gap_ms": int(dt * 1000),
                    "up_px": up_t["price"],
                    "up_sz": max(up_t["size"], round(up_vol, 1)),
                    "up_fill": up_t["size"],
                    "dn_px": dn_t["price"],
                    "dn_sz": max(dn_t["size"], round(dn_vol, 1)),
                    "dn_fill": dn_t["size"],
                    "comb": comb,
                    "profit_usd": round(1.0 - comb, 3),
                    "profit_pct": round(((1.0 - comb)/comb)*100, 1),
                    "dry_up": f"Dried up in {round(dry_up, 1)}s" if dry_up >= 1.0 else f"Dried up in {int(dry_up*1000)}ms"
                })

# Deduplicate identical ticks
deduped = []
seen = set()
for o in opps:
    k = (o["time_utc"], o["up_px"], o["dn_px"], o["comb"])
    if k not in seen:
        deduped.append(o)
        seen.add(k)

print(f"Total Simultaneous Sub-$1.00 Opportunities Found: {len(deduped)}\n", flush=True)

header = f"{'Elapsed (Countdown)':<20} | {'Time (UTC)':<12} | {'UP Available & Price':<26} | {'DOWN Available & Price':<26} | {'Total Cost':<10} | {'Execution Gap':<15} | {'How Soon It Dried Up':<22} | {'Guaranteed Profit'}"
print(header, flush=True)
print("-" * len(header), flush=True)

for d in deduped:
    el_str = f"T+{d['sec']:03d}s (T-{d['countdown']:03d}s)"
    up_s = f"{d['up_sz']:>5.1f} sh (Bt {d['up_fill']:.1f}) @ ${d['up_px']:.2f}"
    dn_s = f"{d['dn_sz']:>5.1f} sh (Bt {d['dn_fill']:.1f}) @ ${d['dn_px']:.2f}"
    cost_s = f"${d['comb']:.3f} ({int(round(d['comb']*100))}¢)"
    gap_s = f"{d['gap_ms']}ms (Instant)" if d['gap_ms'] < 1000 else f"{round(d['gap_ms']/1000,1)}s (Instant)"
    prof_s = f"+${d['profit_usd']:.3f} (+{d['profit_pct']}%)"
    print(f"{el_str:<20} | {d['time_utc']:<12} | {up_s:<26} | {dn_s:<26} | {cost_s:<10} | {gap_s:<15} | {d['dry_up']:<22} | {prof_s}", flush=True)

print("="*150, flush=True)
