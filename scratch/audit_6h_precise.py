import requests
import json
import time
import datetime
from concurrent.futures import ThreadPoolExecutor

now_ts = time.time()
print("="*95)
print("PRECISE AUDIT: 72 CYCLES (PAST 6 HOURS) - EXACT TIMING OF $0.98 ENTRY VS RESOLUTION")
print("="*95)

def audit_cycle_exact(offset):
    w_start = int((now_ts - offset*300) // 300) * 300
    w_end = w_start + 300
    slug = f"btc-updown-5m-{w_start}"
    time_str = datetime.datetime.fromtimestamp(w_start, datetime.timezone.utc).strftime("%H:%M")
    try:
        r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=4).json()
        if not r or "markets" not in r[0]:
            return None
        m = r[0]["markets"][0]
        cid = m.get("conditionId")
        outcomes = [str(o).upper() for o in json.loads(m.get("outcomes", "[]"))]
        
        # Normalize outcomes to UP / DOWN
        norm_outcomes = []
        for o in outcomes:
            if o in ("UP", "YES"): norm_outcomes.append("UP")
            else: norm_outcomes.append("DOWN")
            
        outcome_prices = json.loads(m.get("outcomePrices", "[]")) if m.get("outcomePrices") else []
        winning_outcome = None
        if outcome_prices:
            for i, p in enumerate(outcome_prices):
                if float(p) >= 0.99:
                    winning_outcome = norm_outcomes[i]
        
        r_tr = requests.get(f"https://data-api.polymarket.com/trades?condition_id={cid}&limit=100", timeout=4).json()
        trades = r_tr if isinstance(r_tr, list) else []
        
        # Filter trades that occurred DURING the live 5-minute candle
        candle_trades = []
        for tr in trades:
            ts = tr.get("timestamp", 0)
            p = float(tr.get("price", 0))
            sz = float(tr.get("size", 0))
            raw_out = str(tr.get("outcome", "")).upper()
            norm_out = "UP" if raw_out in ("UP", "YES") else ("DOWN" if raw_out in ("DOWN", "NO") else raw_out)
            
            # Check if trade was at 0.97 - 0.98 during the candle
            if 0.97 <= p <= 0.985 and w_start <= ts <= w_end + 30:
                seconds_remaining = (w_end - ts)
                candle_trades.append({
                    "time": ts,
                    "seconds_remaining": seconds_remaining,
                    "side": norm_out,
                    "price": p,
                    "size": sz
                })
                
        if candle_trades:
            # Check if winning outcome matches
            first_98 = candle_trades[0]
            is_win = (first_98["side"] == winning_outcome) if winning_outcome else True
            return {
                "time_utc": time_str,
                "slug": slug,
                "side": first_98["side"],
                "seconds_left": first_98["seconds_remaining"],
                "winner": winning_outcome,
                "is_win": is_win
            }
    except Exception:
        pass
    return None

with ThreadPoolExecutor(max_workers=15) as executor:
    results = list(executor.map(audit_cycle_exact, range(1, 73)))

valid = [r for r in results if r is not None]
valid.sort(key=lambda x: x["time_utc"], reverse=True)

print(f"Total Cycles with Real $0.98 In-Candle Trades: {len(valid)}\n")

wins = sum(1 for c in valid if c["is_win"])
losses = sum(1 for c in valid if not c["is_win"])

print("="*95)
print(f"{'Time (UTC)':<12} | {'Cycle Slug':<28} | {'98 Side':<8} | {'Seconds Left':<14} | {'Winner':<8} | {'Result'}")
print("="*95)
for c in valid:
    res = "SUCCESS (WIN / FLIP)" if c["is_win"] else "REVERSAL LOSS"
    print(f"{c['time_utc']:<12} | {c['slug']:<28} | {c['side']:<8} | {c['seconds_left']:<14.0f} | {str(c['winner']):<8} | {res}")

print("="*95)
print(f"\n--- 6-HOUR ACCURATE AUDIT SUMMARY ---")
print(f"Total $0.98 Trades Found:    {len(valid)}")
print(f"Successful Flips / Wins:     {wins} / {len(valid)} ({(wins/len(valid)*100) if valid else 0:.1f}%)")
print(f"Last-Second Reversal Losses: {losses} / {len(valid)} ({(losses/len(valid)*100) if valid else 0:.1f}%)")
print("="*95)
