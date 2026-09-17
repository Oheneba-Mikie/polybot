import requests
import json
import time
import datetime
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

DATA_HOST = "https://data-api.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"

print("="*115, flush=True)
print("🔍 STRICT AUDIT: ONLY ORDERS & FILLS THAT ADD UP TO LESS THAN $1.00 (< $1.00)", flush=True)
print("="*115, flush=True)

# Fetch past 3 completed 5-minute markets (15 minutes of trading)
now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - (i * 300) for i in range(1, 4)]

strict_sub_1_events = []

for w_s in windows:
    slug = f"btc-updown-5m-{w_s}"
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
    
    # Strictly find events where UP + DOWN < 1.00
    for i, t1 in enumerate(trades):
        if t1["px"] < 0.05 or t1["px"] > 0.95: continue
        for j in range(i+1, min(i+40, len(trades))):
            t2 = trades[j]
            if t2["px"] < 0.05 or t2["px"] > 0.95: continue
            
            dt = t2["ts"] - t1["ts"]
            if dt > 2.0: break # Only within 2 seconds
            
            # Check opposite sides
            if (t1["out"] in ("UP", "YES") and t2["out"] in ("DOWN", "NO")) or (t1["out"] in ("DOWN", "NO") and t2["out"] in ("UP", "YES")):
                comb = t1["px"] + t2["px"]
                if comb < 0.980: # STRICTLY LESS THAN $1.00
                    up_t = t1 if t1["out"] in ("UP", "YES") else t2
                    dn_t = t2 if t1["out"] in ("UP", "YES") else t1
                    
                    strict_sub_1_events.append({
                        "time_str": datetime.datetime.fromtimestamp(t1["ts"], datetime.timezone.utc).strftime("%H:%M:%S"),
                        "up_shares": up_t["sz"],
                        "up_price": up_t["px"],
                        "dn_shares": dn_t["sz"],
                        "dn_price": dn_t["px"],
                        "time_gap_ms": int(dt * 1000),
                        "total_cost": round(comb, 3),
                        "locked_profit_pct": round(((1.0 - comb) / comb) * 100.0, 1)
                    })

print(f"Found {len(strict_sub_1_events)} real trades that added up to LESS THAN $1.00 (< $1.00):\n")

print(f"{'Time (UTC)':<10} | {'UP Shares Available':<20} | {'UP Price':<10} | {'DOWN Shares Available':<22} | {'DOWN Price':<11} | {'Total Cost (<$1.00)':<20} | {'Locked Profit'}")
print("-" * 115)

for ev in strict_sub_1_events[:20]:
    u_sh = f"{ev['up_shares']:.1f} shares"
    u_p = f"${ev['up_price']:.2f}"
    d_sh = f"{ev['dn_shares']:.1f} shares"
    d_p = f"${ev['dn_price']:.2f}"
    tot = f"${ev['total_cost']:.3f} ({ev['time_gap_ms']}ms gap)"
    prof = f"+{ev['locked_profit_pct']}%"
    print(f"{ev['time_str']:<10} | {u_sh:<20} | {u_p:<10} | {d_sh:<22} | {d_p:<11} | {tot:<20} | {prof}")

print("="*115, flush=True)
