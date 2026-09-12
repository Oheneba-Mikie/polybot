import requests
import json
import time
import datetime
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

DATA_HOST = "https://data-api.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"

print("="*110, flush=True)
print("🔍 AUDIT OF ACTUAL INSTANTANEOUS / SAME-SECOND CROSS-FILLS (< $1.00)", flush=True)
print("="*110, flush=True)

# Fetch recent 20 5-minute markets and check for same-second (<= 1.0s) UP + DOWN buys with sum < 1.00
now = int(time.time())
cur_w = (now // 300) * 300

same_second_arbs = []

for i in range(1, 25):
    ts = cur_w - (i * 300)
    slug = f"btc-updown-5m-{ts}"
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
        if not r or not r[0].get("markets"): continue
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        
        r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=500", timeout=3).json()
        if not r_tr: continue
        
        # Sort trades chronologically
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
                trades.append({"ts": tr_ts, "side": side, "out": outcome, "px": px, "sz": sz})
                
        trades.sort(key=lambda x: x["ts"])
        
        # Find trades occurring within 1.0 second of each other on OPPOSITE sides
        for j in range(len(trades)):
            t1 = trades[j]
            for k in range(j+1, len(trades)):
                t2 = trades[k]
                time_diff = abs(t2["ts"] - t1["ts"])
                if time_diff > 1.5: break # Only check within 1.5 seconds
                
                # Check if opposite outcomes (UP vs DOWN)
                if (t1["out"] in ("UP", "YES") and t2["out"] in ("DOWN", "NO")) or (t1["out"] in ("DOWN", "NO") and t2["out"] in ("UP", "YES")):
                    comb_px = t1["px"] + t2["px"]
                    if comb_px < 0.98 and t1["px"] > 0.05 and t2["px"] > 0.05:
                        t_str = datetime.datetime.fromtimestamp(t1["ts"], datetime.timezone.utc).strftime("%H:%M:%S")
                        same_second_arbs.append({
                            "slug": slug,
                            "time": t_str,
                            "diff_ms": int(time_diff * 1000),
                            "t1_out": t1["out"], "t1_px": t1["px"], "t1_sz": t1["sz"],
                            "t2_out": t2["out"], "t2_px": t2["px"], "t2_sz": t2["sz"],
                            "comb_px": round(comb_px, 3),
                            "profit_pct": round(((1.0 - comb_px)/comb_px)*100, 1)
                        })
    except Exception as e:
        continue

print(f"Audited past 24 markets: Found {len(same_second_arbs)} instances of near-instantaneous (< 1.5s) sub-$0.98 fills!\n")

if same_second_arbs:
    print(f"{'Time (UTC)':<10} | {'Slug':<26} | {'Leg 1':<22} | {'Leg 2':<22} | {'Time Gap':<10} | {'Combined':<9} | {'Profit'}")
    print("-" * 115)
    for a in same_second_arbs[:15]:
        leg1 = f"{a['t1_sz']:.1f} {a['t1_out']} @ ${a['t1_px']:.2f}"
        leg2 = f"{a['t2_sz']:.1f} {a['t2_out']} @ ${a['t2_px']:.2f}"
        gap = f"{a['diff_ms']} ms"
        print(f"{a['time']:<10} | {a['slug']:<26} | {leg1:<22} | {leg2:<22} | {gap:<10} | ${a['comb_px']:<8.3f} | +{a['profit_pct']}%")

print("="*110, flush=True)
