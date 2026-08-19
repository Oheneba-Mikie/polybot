import requests
import json
import time
import datetime
from concurrent.futures import ThreadPoolExecutor

now_ts = time.time()
print("="*95)
print("AUDITING PAST 6 HOURS (72 CYCLES) OF 5-MINUTE BTC MARKETS ON POLYMARKET")
print("ANALYSIS: When $0.97 - $0.98 appeared, did it flip to $0.99 / win, or did a last-second reversal occur?")
print("="*95)

def audit_single_cycle(offset):
    w_start = int((now_ts - offset*300) // 300) * 300
    w_end = w_start + 300
    slug = f"btc-updown-5m-{w_start}"
    time_str = datetime.datetime.fromtimestamp(w_start, datetime.timezone.utc).strftime("%H:%M")
    try:
        r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=4).json()
        if not r or "markets" not in r[0]: return None
        m = r[0]["markets"][0]
        cid = m.get("conditionId")
        outcomes = [str(o).upper() for o in json.loads(m.get("outcomes", "[]"))]
        norm_outcomes = ["UP" if o in ("UP", "YES") else "DOWN" for o in outcomes]
        
        # Check actual winning outcome
        outcome_prices = json.loads(m.get("outcomePrices", "[]")) if m.get("outcomePrices") else []
        winning_outcome = None
        if outcome_prices:
            for i, p in enumerate(outcome_prices):
                if float(p) >= 0.95:
                    winning_outcome = norm_outcomes[i]
                    
        # Fetch trades for this exact market conditionId
        r_tr = requests.get(f"https://data-api.polymarket.com/trades?market={cid}&limit=100", timeout=4).json()
        trades = r_tr if isinstance(r_tr, list) else []
        
        has_98 = False
        trade_side = None
        trade_shares = 0
        has_99_flip = False
        trade_time_left = 0
        
        for tr in trades:
            raw_out = str(tr.get("outcome", "")).upper()
            side = "UP" if raw_out in ("UP", "YES") else ("DOWN" if raw_out in ("DOWN", "NO") else raw_out)
            p = float(tr.get("price", 0))
            sz = float(tr.get("size", 0))
            ts = tr.get("timestamp", 0)
            
            if 0.965 <= p <= 0.985:
                has_98 = True
                trade_side = side
                trade_shares += sz
                trade_time_left = max(0, w_end - ts)
            elif p >= 0.99 and has_98 and side == trade_side:
                has_99_flip = True
                
        if has_98 and winning_outcome:
            is_win = (trade_side == winning_outcome)
            return {
                "time_utc": time_str,
                "slug": slug,
                "side": trade_side,
                "shares": trade_shares,
                "seconds_left": trade_time_left,
                "flipped_99": "YES (Flipped @ $0.99)" if has_99_flip else "HELD TO $1.00",
                "winner": winning_outcome,
                "is_win": is_win
            }
    except Exception:
        pass
    return None

with ThreadPoolExecutor(max_workers=15) as executor:
    results = list(executor.map(audit_single_cycle, range(1, 73)))

valid = [r for r in results if r is not None]
valid.sort(key=lambda x: x["time_utc"], reverse=True)

print(f"\nTotal 5-Minute Cycles Audited: 72 (Past 6 Hours)")
print(f"Total Cycles with Real $0.98 Activity: {len(valid)}\n")

wins = sum(1 for c in valid if c["is_win"])
losses = sum(1 for c in valid if not c["is_win"])

print("="*95)
print(f"{'Time (UTC)':<10} | {'Cycle Slug':<28} | {'98 Side':<8} | {'Shares':<8} | {'Exit Path':<22} | {'Result'}")
print("="*95)
for c in valid:
    res = "SUCCESSFUL WIN / FLIP [WIN]" if c["is_win"] else "REVERSAL LOSS [LOSS]"
    print(f"{c['time_utc']:<10} | {c['slug']:<28} | {c['side']:<8} | {c['shares']:<8.1f} | {c['flipped_99']:<22} | {res}")

print("="*95)
print(f"\n--- 6-HOUR FULL AUDIT RESULTS ---")
print(f"Total $0.98 Trade Opportunities:   {len(valid)}")
print(f"Successful Flips / Resolution Wins: {wins} / {len(valid)} ({(wins/len(valid)*100) if valid else 0:.1f}%)")
print(f"Last-Second Reversal Losses:        {losses} / {len(valid)} ({(losses/len(valid)*100) if valid else 0:.1f}%)")
print("="*95)
