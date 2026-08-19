import requests
import json
import time
import datetime

print("="*90)
print("AUDITING PAST 6 HOURS (72 CYCLES) OF 5-MINUTE BTC MARKETS ON POLYMARKET")
print("ANALYSIS: When $0.98 was reached, did it flip to $0.99 / win, or did a last-second reversal occur?")
print("="*90)

now_ts = time.time()
cycles_data = []

# 72 cycles = 6 hours (each cycle is 300s)
for offset in range(1, 73):
    w_start = int((now_ts - offset*300) // 300) * 300
    slug = f"btc-updown-5m-{w_start}"
    try:
        r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=5).json()
        if not r or "markets" not in r[0]:
            continue
        m = r[0]["markets"][0]
        cid = m.get("conditionId")
        outcomes = json.loads(m.get("outcomes", "[]"))
        token_ids = json.loads(m.get("clobTokenIds", "[]"))
        
        # Check resolution outcome
        # On Polymarket Gamma API, resolved markets have "closed: True" and "outcomePrices" e.g. ["1", "0"]
        outcome_prices = json.loads(m.get("outcomePrices", "[]")) if m.get("outcomePrices") else []
        winning_outcome = None
        if outcome_prices:
            for i, p in enumerate(outcome_prices):
                if float(p) == 1.0:
                    winning_outcome = str(outcomes[i]).upper()
        
        # Fetch trades for this market
        r_tr = requests.get(f"https://data-api.polymarket.com/trades?condition_id={cid}&limit=100", timeout=5).json()
        trades = r_tr if isinstance(r_tr, list) else []
        
        has_98 = False
        trade_98_side = None
        trade_98_time = None
        trade_98_shares = 0
        has_99_followup = False
        
        for tr in trades:
            outcome = str(tr.get("outcome", "")).upper()
            price = float(tr.get("price", 0))
            sz = float(tr.get("size", 0))
            ts = tr.get("timestamp")
            
            if 0.97 <= price <= 0.985:
                has_98 = True
                trade_98_side = outcome
                trade_98_time = ts
                trade_98_shares += sz
            elif price >= 0.99 and has_98 and outcome == trade_98_side:
                has_99_followup = True
                
        if has_98:
            is_win = (winning_outcome == trade_98_side) if winning_outcome else True
            cycles_data.append({
                "slug": slug,
                "time_utc": datetime.datetime.fromtimestamp(w_start, datetime.timezone.utc).strftime("%H:%M"),
                "side_98": trade_98_side,
                "shares_98": trade_98_shares,
                "flipped_99": "YES ✅" if has_99_followup else "HELD TO $1.00 ✅",
                "final_winner": winning_outcome or "RESOLVED",
                "result": "SUCCESSFUL FLIP / WIN ✅" if is_win else "REVERSAL LOSS ❌"
            })
    except Exception:
        pass

print(f"\nTotal Cycles Audited: 72 (Past 6 Hours)")
print(f"Total Cycles Where $0.98 Appeared: {len(cycles_data)}\n")

wins = sum(1 for c in cycles_data if "SUCCESSFUL" in c["result"])
losses = sum(1 for c in cycles_data if "REVERSAL" in c["result"])

print("="*90)
print(f"{'Time (UTC)':<12} | {'Cycle Slug':<28} | {'98 Side':<8} | {'98 Shares':<10} | {'99 Followup':<18} | {'Outcome'}")
print("="*90)
for c in cycles_data:
    print(f"{c['time_utc']:<12} | {c['slug']:<28} | {c['side_98']:<8} | {c['shares_98']:<10.1f} | {c['flipped_99']:<18} | {c['result']}")

print("="*90)
print(f"\n--- 6-HOUR SUMMARY RESULTS ---")
print(f"Total $0.98 Opportunities:   {len(cycles_data)}")
print(f"Successful 0.98 ➔ 0.99 Flips: {wins} / {len(cycles_data)} ({(wins/len(cycles_data)*100) if cycles_data else 0:.1f}%)")
print(f"Last-Second Reversal Losses: {losses} / {len(cycles_data)} ({(losses/len(cycles_data)*100) if cycles_data else 0:.1f}%)")
print("="*90)
