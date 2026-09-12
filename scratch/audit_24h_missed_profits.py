import requests
import json
import datetime
import time
import sys
import math
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# Current time: Aug 25, 2026 ~10:15 UTC
# 24 hours ago: Aug 24, 2026 10:30 UTC
now = int(time.time())
start_24h = now - (24 * 3600)
# round to 300s window start
start_ts = int(start_24h // 300) * 300

timestamps = list(range(start_ts, now - 300, 300))

print("="*95)
print(f"📊 24-HOUR OPPORTUNITY & PROFIT AUDIT: 99¢ LATE-CANDLE SNIPER ({len(timestamps)} CANDLES)")
print("="*95)

def analyze_candle(ts):
    slug = f"btc-updown-5m-{ts}"
    candle_end = ts + 300
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%m/%d %H:%M UTC")
    
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
        if not r or not r[0].get("markets"): return None
        
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        outcome_prices_raw = mkt.get("outcomePrices", "[]")
        outcome_prices = json.loads(outcome_prices_raw) if isinstance(outcome_prices_raw, str) else outcome_prices_raw
        
        # Winner
        winner = "UP" if outcome_prices and float(outcome_prices[0]) > 0.9 else ("DOWN" if outcome_prices and len(outcome_prices)>1 and float(outcome_prices[1]) > 0.9 else "UNKNOWN")
        
        r_trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=100", timeout=3).json()
        
        sniped = False
        sniped_side = None
        sniped_price = None
        time_left_when_sniped = None
        
        # Check trades in final 90s (between candle_end - 90 and candle_end - 10)
        for t in reversed(r_trades): # chronological
            t_sec = t.get("timestamp", 0)
            time_left = candle_end - t_sec
            px = float(t.get("price", 0))
            out = str(t.get("outcome", "")).upper()
            
            if 10.0 <= time_left <= 90.0:
                if 0.980 <= px <= 0.990:
                    sniped = True
                    sniped_side = out
                    sniped_price = px
                    time_left_when_sniped = time_left
                    break
                    
        is_win = False
        is_loss = False
        if sniped:
            if sniped_side == winner:
                is_win = True
            else:
                is_loss = True
                
        return {
            "ts": ts,
            "time": dt_str,
            "slug": slug,
            "winner": winner,
            "sniped": sniped,
            "sniped_side": sniped_side,
            "sniped_price": sniped_price,
            "time_left": time_left_when_sniped,
            "is_win": is_win,
            "is_loss": is_loss
        }
    except:
        return None

print(f"Pulling order book and trade data for {len(timestamps)} past candles...")
with ThreadPoolExecutor(max_workers=25) as executor:
    results = list(executor.map(analyze_candle, timestamps))

records = sorted([r for r in results if r is not None], key=lambda x: x["ts"])

total_audited = len(records)
snipes_available = sum(1 for r in records if r["sniped"])
clean_wins = sum(1 for r in records if r["is_win"])
losses = sum(1 for r in records if r["is_loss"])

# Simulation calculations:
# Base test: 5 shares per trade ($4.95 stake per trade)
fixed_profit = (clean_wins * 5 * 0.01) - (losses * 5 * 0.99)

# Compounding Simulation starting with $5.00 bankroll (all-in compounding)
bankroll_5 = 5.00
for r in records:
    if r["sniped"]:
        if r["is_win"]:
            # Yield is ~1.01%
            shares = math.floor(bankroll_5 / (r["sniped_price"] or 0.99))
            profit = shares * (1.00 - (r["sniped_price"] or 0.99))
            bankroll_5 += profit
        elif r["is_loss"]:
            bankroll_5 = 0.0

# Compounding Simulation starting with $50 bankroll
bankroll_50 = 50.00
for r in records:
    if r["sniped"]:
        if r["is_win"]:
            shares = math.floor(bankroll_50 / (r["sniped_price"] or 0.99))
            profit = shares * (1.00 - (r["sniped_price"] or 0.99))
            bankroll_50 += profit

print("="*95)
print(f"{'Candle Time':<18} | {'Winner':<6} | {'Snipe Status':<15} | {'Price':<8} | {'Time Left':<10} | {'Outcome'}")
print("-" * 95)
for r in records[-25:]: # last 25 candles
    if r["sniped"]:
        stat = f"🎯 {r['sniped_side']}"
        px_s = f"${r['sniped_price']:.3f}"
        tl_s = f"{r['time_left']:.0f}s left"
        res_s = "🏆 +1.01% WIN ($1.00)" if r["is_win"] else "❌ LOSS"
    else:
        stat = "⚪ No 99¢ in T-90s"
        px_s = "-"
        tl_s = "-"
        res_s = "-"
    print(f"{r['time']:<18} | {r['winner']:<6} | {stat:<15} | {px_s:<8} | {tl_s:<10} | {res_s}")

print("="*95)
print("📊 24-HOUR 99¢ SNIPER BACKTEST PERFORMANCE RESULTS:")
print(f"- Total 5-Minute Candles Audited:        {total_audited}")
print(f"- Confirmed 99¢ Snipe Opportunities:     {snipes_available} / {total_audited} ({(snipes_available/max(1,total_audited))*100:.1f}%)")
print(f"- Successful Wins (Resolved to $1.00):   {clean_wins} / {max(1, snipes_available)} ({(clean_wins/max(1,snipes_available))*100:.1f}% Win Rate)")
print(f"- Failed Snipes / Reversals:             {losses}")
print("-" * 95)
print(f"💰 PROFIT POTENTIAL OVER PAST 24 HOURS:")
print(f"1. Fixed 5-Share Bet ($4.95/trade):       +${fixed_profit:.2f} Net Cash Profit ({clean_wins} wins x +$0.05)")
print(f"2. Compounded Starting Bankroll of $5.00:  $5.00  -->  ${bankroll_5:.2f} USDC (+{((bankroll_5-5)/5)*100:.1f}%)")
print(f"3. Compounded Starting Bankroll of $50.00: $50.00 -->  ${bankroll_50:.2f} USDC (+{((bankroll_50-50)/50)*100:.1f}%)")
print("="*95)
