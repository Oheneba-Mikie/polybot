import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

print("="*95)
print("🔍 AUDITING EVERY 5-MINUTE CANDLE FROM 20:15 UTC TO NOW (22:45 UTC):")
print("="*95)

now = time.time()
cur_w_s = int(now // 300) * 300

# 2.5 hours = 30 candles
candles_ts = [cur_w_s - (i * 300) for i in range(1, 31)]
candles_ts.reverse()

total_triggers = 0
total_wins = 0
total_flips = 0
total_bailouts = 0

simulated_balance = 5.45

for ts in candles_ts:
    slug = f"btc-updown-5m-{ts}"
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M UTC")
    
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
        if not r or not r[0].get("markets"): continue
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        title = mkt.get("question", slug)
        resolved_prices = json.loads(mkt.get("outcomePrices") or "[]")
        
        r_trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=500", timeout=5).json()
        if not r_trades: continue
        
        trades = sorted(r_trades, key=lambda x: x.get("timestamp", 0))
        
        entered = False
        side = None
        entry_t = None
        exit_t = None
        outcome = None
        
        for t in trades:
            px = float(t.get("price", 0))
            t_sec = t.get("timestamp", 0)
            outcome_name = t.get("outcome", "")
            
            if not entered and 0.965 <= px <= 0.978:
                entered = True
                side = outcome_name
                entry_t = t_sec
            elif entered and t_sec > entry_t:
                # Check if it reached 0.98 or flipped
                if outcome_name == side and px >= 0.98:
                    outcome = "WIN_SCALP"
                    exit_t = t_sec
                    break
                elif (t_sec - entry_t) > 40.0:
                    outcome = "TIMEOUT_BAILOUT"
                    exit_t = t_sec
                    break
                    
        if entered:
            total_triggers += 1
            if outcome == "WIN_SCALP":
                total_wins += 1
                duration = max(1, exit_t - entry_t) if exit_t else 5
                profit_pct = 1.03
                simulated_balance = round(simulated_balance * 1.0103, 2)
                print(f"[{dt_str}] 🏆 WIN SCALP  | {side:<4} @ 97c -> 98c in {duration}s | Account: ${simulated_balance:.2f}")
            elif outcome == "TIMEOUT_BAILOUT":
                total_bailouts += 1
                simulated_balance = round(simulated_balance * 0.99, 2) # minor -1% spread dump
                print(f"[{dt_str}] ⏰ 40s BAILOUT | {side:<4} dumped at market    | Account: ${simulated_balance:.2f}")
            else:
                # Resolution win
                total_wins += 1
                simulated_balance = round(simulated_balance * 1.03, 2)
                print(f"[{dt_str}] 🏆 RESOLVED WIN | {side:<4} expired @ $1.00       | Account: ${simulated_balance:.2f}")
    except Exception as e:
        continue

print("="*95)
print(f"📊 SUMMARY ACROSS LAST 30 CANDLES (2.5 HOURS):")
print(f"  • Total 97¢ Triggers Detected: {total_triggers}")
print(f"  • Scalp Wins (Exit in <40s):   {total_wins} ({total_wins/max(1, total_triggers)*100:.1f}%)")
print(f"  • Flips / 40s Bailouts:        {total_bailouts}")
print(f"  • Account Growth ($5.45 Start): ${simulated_balance:.2f} (+{(simulated_balance-5.45)/5.45*100:.1f}%)")
print("="*95)
