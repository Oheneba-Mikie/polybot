import requests
import json
import time
import datetime
from concurrent.futures import ThreadPoolExecutor

now_ts = time.time()
print("="*90)
print("FAST PARALLEL AUDIT: 72 CYCLES (PAST 6 HOURS) ON POLYMARKET")
print("="*90)

def audit_cycle(offset):
    w_start = int((now_ts - offset*300) // 300) * 300
    slug = f"btc-updown-5m-{w_start}"
    time_str = datetime.datetime.fromtimestamp(w_start, datetime.timezone.utc).strftime("%H:%M")
    try:
        r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=4).json()
        if not r or "markets" not in r[0]:
            return None
        m = r[0]["markets"][0]
        cid = m.get("conditionId")
        outcomes = json.loads(m.get("outcomes", "[]"))
        
        # Check resolution winner
        outcome_prices = json.loads(m.get("outcomePrices", "[]")) if m.get("outcomePrices") else []
        winning_outcome = None
        if outcome_prices:
            for i, p in enumerate(outcome_prices):
                if float(p) == 1.0:
                    winning_outcome = str(outcomes[i]).upper()
        
        # Fetch trades
        r_tr = requests.get(f"https://data-api.polymarket.com/trades?condition_id={cid}&limit=100", timeout=4).json()
        trades = r_tr if isinstance(r_tr, list) else []
        
        has_98 = False
        trade_98_side = None
        trade_98_shares = 0
        has_99_followup = False
        
        for tr in trades:
            outcome = str(tr.get("outcome", "")).upper()
            price = float(tr.get("price", 0))
            sz = float(tr.get("size", 0))
            
            if 0.97 <= price <= 0.985:
                has_98 = True
                trade_98_side = outcome
                trade_98_shares += sz
            elif price >= 0.99 and has_98 and outcome == trade_98_side:
                has_99_followup = True
                
        if has_98:
            is_win = (winning_outcome == trade_98_side) if winning_outcome else True
            return {
                "time_utc": time_str,
                "slug": slug,
                "side_98": trade_98_side,
                "shares_98": trade_98_shares,
                "flipped_99": "YES (at $0.99)" if has_99_followup else "HELD TO $1.00",
                "result": "SUCCESSFUL WIN / FLIP" if is_win else "REVERSAL LOSS",
                "is_win": is_win
            }
    except Exception:
        return None

with ThreadPoolExecutor(max_workers=15) as executor:
    results = list(executor.map(audit_cycle, range(1, 73)))

cycles_data = [r for r in results if r is not None]
cycles_data.sort(key=lambda x: x["time_utc"], reverse=True)

print(f"Total Cycles Audited: 72")
print(f"Total Cycles Where $0.98 Appeared: {len(cycles_data)}\n")

wins = sum(1 for c in cycles_data if c["is_win"])
losses = sum(1 for c in cycles_data if not c["is_win"])

print("="*95)
print(f"{'Time (UTC)':<10} | {'Cycle Slug':<28} | {'98 Side':<8} | {'98 Shares':<10} | {'Exit Path':<20} | {'Result'}")
print("="*95)
for c in cycles_data:
    print(f"{c['time_utc']:<10} | {c['slug']:<28} | {c['side_98']:<8} | {c['shares_98']:<10.1f} | {c['flipped_99']:<20} | {c['result']}")

print("="*95)
print(f"\n--- 6-HOUR AUDIT SUMMARY ---")
print(f"Total $0.98 Appearances:     {len(cycles_data)}")
print(f"Successful Flips / Wins:     {wins} / {len(cycles_data)} ({(wins/len(cycles_data)*100) if cycles_data else 0:.1f}%)")
print(f"Last-Second Reversal Losses: {losses} / {len(cycles_data)} ({(losses/len(cycles_data)*100) if cycles_data else 0:.1f}%)")
print("="*95)
