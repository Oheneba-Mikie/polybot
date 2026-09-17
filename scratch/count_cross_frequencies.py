import requests
import json
import time
import datetime
import statistics

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - (i * 300) for i in range(1, 13)] # last 12 windows (past 1 hour)
windows.reverse()

results = []

for w in windows:
    slug = f"eth-updown-5m-{w}"
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r or not r[0].get("markets"):
            continue
        cid = r[0]["markets"][0].get("conditionId")
        trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=2000", timeout=4).json()
        if not isinstance(trades, list):
            continue
        
        parsed = []
        for t in trades:
            ts = t.get("timestamp") or t.get("matchTime")
            if isinstance(ts, str):
                try:
                    ts = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() if "T" in ts else float(ts)
                except Exception:
                    ts = 0
            if ts and ts > 1e11:
                ts /= 1000.0
            if w <= ts <= w + 300:
                parsed.append({
                    "ts": ts,
                    "sec": int(ts - w),
                    "p": float(t.get("price", 0)),
                    "s": float(t.get("size", 0)),
                    "o": str(t.get("outcome", "")).upper()
                })
        parsed.sort(key=lambda x: x["ts"])
        
        crosses_995 = 0
        crosses_980 = 0
        crosses_950 = 0
        first_min = 0
        mid_3m = 0
        final_min = 0
        
        for i, t1 in enumerate(parsed):
            for j in range(i + 1, min(i + 40, len(parsed))):
                t2 = parsed[j]
                if t2["ts"] - t1["ts"] > 1.5:
                    break
                if (t1["o"] in ("UP","YES") and t2["o"] in ("DOWN","NO")) or (t1["o"] in ("DOWN","NO") and t2["o"] in ("UP","YES")):
                    c = round(t1["p"] + t2["p"], 3)
                    if c <= 0.995:
                        crosses_995 += 1
                        if c <= 0.980: crosses_980 += 1
                        if c <= 0.950: crosses_950 += 1
                        
                        sec = t1["sec"]
                        if sec <= 60: first_min += 1
                        elif sec >= 240: final_min += 1
                        else: mid_3m += 1
        
        results.append({
            "slug": slug,
            "time_utc": datetime.datetime.fromtimestamp(w, datetime.timezone.utc).strftime("%H:%M"),
            "total_trades": len(parsed),
            "crosses_995": crosses_995,
            "crosses_980": crosses_980,
            "crosses_950": crosses_950,
            "first_min": first_min,
            "mid_3m": mid_3m,
            "final_min": final_min
        })
    except Exception as e:
        pass

print(f"=== EMPIRICAL AUDIT: CROSS FREQUENCY ACROSS {len(results)} PAST ETH 5M CANDLES ===")
header = f"{'Candle Time':<12} | {'Total Trades':<12} | {'<= $0.995':<12} | {'<= $0.980':<12} | {'<= $0.950':<12} | {'T<60s':<8} | {'T 60-240s':<10} | {'Final 60s':<10}"
print(header)
print("-" * len(header))
for r in results:
    row = f"{r['time_utc']} UTC    | {r['total_trades']:<12d} | {r['crosses_995']:<12d} | {r['crosses_980']:<12d} | {r['crosses_950']:<12d} | {r['first_min']:<8d} | {r['mid_3m']:<10d} | {r['final_min']:<10d}"
    print(row)

c995 = [r["crosses_995"] for r in results]
if c995:
    print("-" * len(header))
    print(f"AVERAGE CROSSES <= $0.995 PER 5M WINDOW : {statistics.mean(c995):.1f}")
    print(f"MEDIAN CROSSES <= $0.995 PER 5M WINDOW  : {statistics.median(c995):.1f}")
    print(f"MIN PER 5M WINDOW                      : {min(c995)}")
    print(f"MAX PER 5M WINDOW                      : {max(c995)}")
    
    # Timing distribution
    tot_c = sum(c995)
    tot_first = sum(r["first_min"] for r in results)
    tot_mid   = sum(r["mid_3m"] for r in results)
    tot_final = sum(r["final_min"] for r in results)
    print("\n--- TIMING DISTRIBUTION WITHIN THE 5-MINUTE CANDLE ---")
    print(f"First 60s (Candle Open)       : {tot_first} crosses ({tot_first/tot_c*100:.1f}%)")
    print(f"Middle 3 Minutes (T+60 to 240): {tot_mid} crosses ({tot_mid/tot_c*100:.1f}%)")
    print(f"Final 60s (Expiry Climax)     : {tot_final} crosses ({tot_final/tot_c*100:.1f}%)")
