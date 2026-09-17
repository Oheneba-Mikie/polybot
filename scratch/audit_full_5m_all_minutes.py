import requests
import json
import time
import datetime
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

w_s = 1789213800 # 11:50:00 UTC
slug = f"btc-updown-5m-{w_s}"

r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
cid = r_evt[0]['markets'][0]['conditionId']

r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=1000", timeout=5).json()

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

print("="*145)
print(f"📊 FULL 5-MINUTE AUDIT: MINUTE-BY-MINUTE BREAKDOWN (11:50:00 - 11:55:00 UTC) | Total Trades: {len(trades)}")
print("="*145)

# Group trades by minute: 11:50, 11:51, 11:52, 11:53, 11:54
for m_idx in range(5):
    m_start = w_s + m_idx * 60
    m_end = m_start + 60
    m_name = datetime.datetime.fromtimestamp(m_start, datetime.timezone.utc).strftime("%H:%M")
    
    m_trades = [t for t in trades if m_start <= t["ts"] < m_end]
    print(f"\n>>> MINUTE {m_name} UTC (T-{300 - m_idx*60}s to T-{300 - (m_idx+1)*60}s) — Trades in Minute: {len(m_trades)}")
    
    if not m_trades:
        print(f"    No trades occurred during {m_name} UTC (market was waiting for wave / holding quotes).")
        continue

    # Find sub-1.00 combinations or key price levels during this specific minute
    results = []
    for i, t1 in enumerate(m_trades):
        # Look within this minute and the next minute for matching leg
        candidates = [t for t in trades if abs(t["ts"] - t1["ts"]) <= 45.0 and t["ts"] >= t1["ts"]]
        for t2 in candidates:
            if (t1["out"] in ("UP", "YES") and t2["out"] in ("DOWN", "NO")) or (t1["out"] in ("DOWN", "NO") and t2["out"] in ("UP", "YES")):
                comb = t1["px"] + t2["px"]
                if comb <= 0.980:
                    dt = t2["ts"] - t1["ts"]
                    up_t = t1 if t1["out"] in ("UP", "YES") else t2
                    dn_t = t2 if t1["out"] in ("UP", "YES") else t1
                    
                    up_cluster = [t for t in trades if t["out"] in ("UP", "YES") and abs(t["px"] - up_t["px"]) <= 0.02 and abs(t["ts"] - up_t["ts"]) <= 10.0]
                    dn_cluster = [t for t in trades if t["out"] in ("DOWN", "NO") and abs(t["px"] - dn_t["px"]) <= 0.02 and abs(t["ts"] - dn_t["ts"]) <= 10.0]
                    
                    up_vol = sum(t["sz"] for t in up_cluster)
                    dn_vol = sum(t["sz"] for t in dn_cluster)
                    
                    up_span = max(0.5, round(max(t["ts"] for t in up_cluster) - min(t["ts"] for t in up_cluster), 1)) if up_cluster else 0.5
                    dn_span = max(0.5, round(max(t["ts"] for t in dn_cluster) - min(t["ts"] for t in dn_cluster), 1)) if dn_cluster else 0.5
                    
                    t1_str = datetime.datetime.fromtimestamp(t1["ts"], datetime.timezone.utc).strftime("%H:%M:%S")
                    t2_str = datetime.datetime.fromtimestamp(t2["ts"], datetime.timezone.utc).strftime("%H:%M:%S")
                    
                    results.append({
                        "time_range": f"[{t1_str} -> {t2_str}]",
                        "up_px": up_t["px"],
                        "up_fill": up_t["sz"],
                        "up_avail": max(up_t["sz"], round(up_vol, 1)),
                        "up_dry": f"Dried up in {up_span}s" if up_span > 0.5 else "Dried up in <1s",
                        "dn_px": dn_t["px"],
                        "dn_fill": dn_t["sz"],
                        "dn_avail": max(dn_t["sz"], round(dn_vol, 1)),
                        "dn_dry": f"Dried up in {dn_span}s" if dn_span > 0.5 else "Dried up in <1s",
                        "comb": round(comb, 3),
                        "dt": round(dt, 1),
                        "profit_pct": round(((1.0 - comb) / comb) * 100.0, 1),
                        "profit_usd": round(1.0 - comb, 3)
                    })
                    
    deduped = []
    seen = set()
    for r in results:
        k = (r["time_range"], r["comb"])
        if k not in seen:
            deduped.append(r)
            seen.add(k)
            
    if not deduped:
        # Show the dominant prices that were trading in this minute if no dual-leg cross formed
        up_in_m = [t for t in m_trades if t["out"] in ("UP", "YES")]
        dn_in_m = [t for t in m_trades if t["out"] in ("DOWN", "NO")]
        print(f"    Trades in this minute were one-sided / directional:")
        if up_in_m:
            avg_p = sum(t["px"]*t["sz"] for t in up_in_m)/sum(t["sz"] for t in up_in_m)
            tot_sz = sum(t["sz"] for t in up_in_m)
            print(f"    - UP Side: {len(up_in_m)} fills | Total Vol: {tot_sz:.1f} sh | Avg Price: ${avg_p:.2f}")
        if dn_in_m:
            avg_p = sum(t["px"]*t["sz"] for t in dn_in_m)/sum(t["sz"] for t in dn_in_m)
            tot_sz = sum(t["sz"] for t in dn_in_m)
            print(f"    - DOWN Side: {len(dn_in_m)} fills | Total Vol: {tot_sz:.1f} sh | Avg Price: ${avg_p:.2f}")
    else:
        print(f"    {'Exact Timestamps (UTC)':<22} | {'UP Shares & Price':<24} | {'UP Dry-Up':<16} | {'DOWN Shares & Price':<24} | {'DOWN Dry-Up':<16} | {'Total Cost':<10} | {'Time Gap':<9} | {'Guaranteed Profit'}")
        print("    " + "-" * 140)
        for d in deduped[:5]:
            up_s = f"{d['up_avail']:>5.1f} sh (Bt {d['up_fill']:.1f}) @ ${d['up_px']:.2f}"
            dn_s = f"{d['dn_avail']:>5.1f} sh (Bt {d['dn_fill']:.1f}) @ ${d['dn_px']:.2f}"
            cost_s = f"${d['comb']:.3f} ({int(round(d['comb']*100))}¢)"
            gap_s = f"{d['dt']}s"
            prof_s = f"+${d['profit_usd']:.3f} (+{d['profit_pct']}%)"
            print(f"    {d['time_range']:<22} | {up_s:<24} | {d['up_dry']:<16} | {dn_s:<24} | {d['dn_dry']:<16} | {cost_s:<10} | {gap_s:<9} | {prof_s}")

print("\n" + "="*145)
