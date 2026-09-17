import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
TARGET_ASSET = "eth"

now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - (i * 300) for i in range(1, 30)]

print("=" * 80)
print(f"EMPIRICAL ANALYSIS: COMPARISON OF LEG 1 ENTRY THRESHOLDS ACROSS {len(windows)} ETH 5M CANDLES")
print("=" * 80)

candle_data = []

for w_s in windows:
    slug = f"{TARGET_ASSET}-updown-5m-{w_s}"
    try:
        r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3.5).json()
        if not r_evt or not r_evt[0].get("markets"):
            continue
        cid = r_evt[0]["markets"][0].get("conditionId")
        if not cid:
            continue
            
        trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=2000", timeout=4.0).json()
        if not isinstance(trades, list) or len(trades) < 5:
            continue
            
        parsed = []
        for t in trades:
            tr_ts = t.get("timestamp") or t.get("matchTime")
            if isinstance(tr_ts, str):
                try:
                    tr_ts = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00")).timestamp() if "T" in tr_ts else float(tr_ts)
                except Exception:
                    tr_ts = 0
            if tr_ts and tr_ts > 1e11:
                tr_ts /= 1000.0
            if w_s <= tr_ts <= w_s + 300:
                raw_out = str(t.get("outcome", "")).upper()
                outcome = "UP" if raw_out in ("UP", "YES") else ("DOWN" if raw_out in ("DOWN", "NO") else "")
                if not outcome:
                    continue
                price = float(t.get("price", 0.0))
                size = float(t.get("size", 0.0))
                if price > 0 and size >= 3.0:
                    parsed.append({"ts": tr_ts, "sec": int(tr_ts - w_s), "outcome": outcome, "price": price, "size": size})
                    
        parsed.sort(key=lambda x: x["ts"])
        if len(parsed) >= 10:
            candle_data.append({"slug": slug, "trades": parsed})
    except Exception:
        continue

print(f"Loaded {len(candle_data)} completed ETH 5M candles with full trade history.\n")

thresholds = [0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.35, 0.45]

print(f"{'Entry Thresh':<14} | {'Triggers':<9} | {'Hedged':<8} | {'Hedge Rate':<12} | {'Median Gap':<12} | {'Avg Delay':<11} | {'Avg Pair Cost'}")
print("-" * 92)

for th in thresholds:
    attempts = 0
    successes = 0
    delays = []
    costs = []
    
    for c in candle_data:
        trades = c["trades"]
        # Find first Leg 1 trade where price <= th (occurring before T-45s)
        leg1 = None
        for t in trades:
            if t["sec"] < 255 and t["price"] <= th:
                leg1 = t
                break
                
        if leg1:
            attempts += 1
            needed_price = round(0.99 - leg1["price"], 3)
            opp_outcome = "DOWN" if leg1["outcome"] == "UP" else "UP"
            
            # Look for opposing leg after leg1 in the same candle
            leg2 = None
            for t2 in trades:
                if t2["ts"] >= leg1["ts"] and t2["outcome"] == opp_outcome and t2["price"] <= needed_price:
                    leg2 = t2
                    break
                    
            if leg2:
                successes += 1
                dt = round(leg2["ts"] - leg1["ts"], 1)
                delays.append(dt)
                comb_cost = round(leg1["price"] + leg2["price"], 3)
                costs.append(comb_cost)
                
    rate = (successes / attempts * 100) if attempts > 0 else 0
    avg_d = (sum(delays) / len(delays)) if delays else 0
    med_d = sorted(delays)[len(delays)//2] if delays else 0
    avg_c = (sum(costs) / len(costs)) if costs else 0
    
    print(f"${th:.2f} (<= {int(th*100):02d}¢)   | {attempts:<9} | {successes:<8} | {rate:>7.1f}%     | {med_d:>6.1f}s     | {avg_d:>6.1f}s    | ${avg_c:.3f}")

print("=" * 92)
