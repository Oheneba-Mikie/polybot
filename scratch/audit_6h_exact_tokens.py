import requests
import json
import time
import datetime
from concurrent.futures import ThreadPoolExecutor

now_ts = time.time()
print("="*95)
print("ACCURATE AUDIT: PAST 6 HOURS (72 CYCLES) OF 5-MINUTE BTC MARKETS ON POLYMARKET")
print("ANALYSIS: Trades executed at $0.97 - $0.99 and whether they flipped/won or reversed")
print("="*95)

def check_cycle(offset):
    w_start = int((now_ts - offset*300) // 300) * 300
    slug = f"btc-updown-5m-{w_start}"
    time_str = datetime.datetime.fromtimestamp(w_start, datetime.timezone.utc).strftime("%H:%M")
    try:
        r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=4).json()
        if not r or "markets" not in r[0]: return None
        m = r[0]["markets"][0]
        cid = m.get("conditionId")
        outcomes = [str(o).upper() for o in json.loads(m.get("outcomes", "[]"))]
        
        # Outcome normalization
        norm_outcomes = ["UP" if o in ("UP", "YES") else "DOWN" for o in outcomes]
        outcome_prices = json.loads(m.get("outcomePrices", "[]")) if m.get("outcomePrices") else []
        
        winning_outcome = None
        if outcome_prices:
            for i, p in enumerate(outcome_prices):
                if float(p) >= 0.99:
                    winning_outcome = norm_outcomes[i]
                    
        # Token IDs
        tids = json.loads(m.get("clobTokenIds", "[]"))
        
        # Query Polymarket CLOB trade history for both tokens
        has_98 = False
        trade_side = None
        trade_shares = 0
        
        for i, tid in enumerate(tids):
            side = norm_outcomes[i]
            r_tr = requests.get(f"https://data-api.polymarket.com/trades?asset_id={tid}&limit=50", timeout=4).json()
            if isinstance(r_tr, list):
                for tr in r_tr:
                    p = float(tr.get("price", 0))
                    sz = float(tr.get("size", 0))
                    if 0.97 <= p <= 0.985:
                        has_98 = True
                        trade_side = side
                        trade_shares += sz
                        
        if has_98 and winning_outcome:
            is_win = (trade_side == winning_outcome)
            return {
                "time_utc": time_str,
                "slug": slug,
                "side": trade_side,
                "shares": trade_shares,
                "winner": winning_outcome,
                "is_win": is_win
            }
    except Exception:
        pass
    return None

with ThreadPoolExecutor(max_workers=15) as executor:
    results = list(executor.map(check_cycle, range(1, 73)))

valid = [r for r in results if r is not None]
valid.sort(key=lambda x: x["time_utc"], reverse=True)

print(f"Total Resolved Cycles with $0.98 Trades Found: {len(valid)}\n")

wins = sum(1 for c in valid if c["is_win"])
losses = sum(1 for c in valid if not c["is_win"])

print("="*95)
print(f"{'Time (UTC)':<10} | {'Cycle Slug':<28} | {'98 Side':<8} | {'Winner':<8} | {'Result'}")
print("="*95)
for c in valid:
    res = "SUCCESS (FLIP / WIN @ $1.00) [WIN]" if c["is_win"] else "REVERSAL LOSS [LOSS]"
    print(f"{c['time_utc']:<10} | {c['slug']:<28} | {c['side']:<8} | {str(c['winner']):<8} | {res}")

print("="*95)
print(f"\n--- 6-HOUR ACCURATE AUDIT SUMMARY ---")
print(f"Total Cycles with $0.98 Appearances: {len(valid)}")
print(f"Successful Flips / Wins:            {wins} / {len(valid)} ({(wins/len(valid)*100) if valid else 0:.1f}%)")
print(f"Last-Second Reversal Losses:        {losses} / {len(valid)} ({(losses/len(valid)*100) if valid else 0:.1f}%)")
print("="*95)
