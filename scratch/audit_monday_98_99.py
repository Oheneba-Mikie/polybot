import requests
import json
import datetime
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# Current time: Monday Aug 24, 2026 ~09:00 UTC
# Monday 00:00 UTC timestamp:
now = int(time.time())
monday_start = int(datetime.datetime(2026, 8, 24, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp())

print("="*95)
print(f"📊 FULL MONDAY (AUG 24, 2026) POLYMARKET 5-MINUTE BTC CANDLE AUDIT (00:00 UTC - NOW)")
print("="*95)

total_candles = 0
candles_98_plus = 0
clean_wins_from_98 = 0
reversals_from_98 = 0

detailed_records = []

# Loop through all 5m candles from monday_start to now
for ts in range(monday_start, now - 300, 300):
    slug = f"btc-updown-5m-{ts}"
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M UTC")
    
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r or not r[0].get("markets"):
            continue
            
        mkt = r[0]["markets"][0]
        question = mkt.get("question", "")
        resolved = mkt.get("resolved")
        closed = mkt.get("closed")
        outcome_prices_raw = mkt.get("outcomePrices", "[]")
        outcome_prices = json.loads(outcome_prices_raw) if isinstance(outcome_prices_raw, str) else outcome_prices_raw
        
        # Get market trades to see price progression
        clob_tokens = json.loads(mkt.get("clobTokenIds", "[]"))
        if not clob_tokens:
            continue
            
        total_candles += 1
        
        up_id = clob_tokens[0]
        dn_id = clob_tokens[1] if len(clob_tokens) > 1 else None
        
        # Check trades on gamma/data API for this market
        r_trades = requests.get(f"{DATA_HOST}/trades?market={mkt.get('conditionId')}&limit=100", timeout=4).json()
        
        max_up_px = 0.0
        max_dn_px = 0.0
        trade_count = len(r_trades)
        
        for t in r_trades:
            px = float(t.get("price", 0))
            out = str(t.get("outcome", "")).lower()
            if out in ("up", "yes"):
                max_up_px = max(max_up_px, px)
            elif out in ("down", "no"):
                max_dn_px = max(max_dn_px, px)
                
        peak_price = max(max_up_px, max_dn_px)
        winner = "UP" if outcome_prices and float(outcome_prices[0]) > 0.9 else ("DOWN" if outcome_prices and len(outcome_prices)>1 and float(outcome_prices[1]) > 0.9 else "UNKNOWN")
        
        hit_98 = peak_price >= 0.98
        if hit_98:
            candles_98_plus += 1
            # Did the token that hit 0.98 win?
            token_hit = "UP" if max_up_px >= 0.98 else "DOWN"
            if token_hit == winner:
                clean_wins_from_98 += 1
                status_str = "✅ WON (1.00)"
            else:
                reversals_from_98 += 1
                status_str = "❌ REVERSED (0.00)"
        else:
            status_str = f"⚪ Peak: ${peak_price:.2f}"
            
        detailed_records.append({
            "time": dt_str,
            "slug": slug,
            "winner": winner,
            "max_up": max_up_px,
            "max_dn": max_dn_px,
            "peak": peak_price,
            "hit_98": hit_98,
            "status": status_str,
            "trades": trade_count
        })
        
    except Exception as e:
        continue

print(f"{'Candle Time':<12} | {'Winner':<6} | {'Peak UP Px':<11} | {'Peak DN Px':<11} | {'Overall Peak':<12} | {'98¢/99¢ Status':<18} | Trades")
print("-" * 95)
for rec in detailed_records[-35:]:  # show last 35 candles
    print(f"{rec['time']:<12} | {rec['winner']:<6} | ${rec['max_up']:<10.3f} | ${rec['max_dn']:<10.3f} | ${rec['peak']:<11.3f} | {rec['status']:<18} | {rec['trades']}")

print("="*95)
print(f"📊 MONDAY AGGREGATE PERFORMANCE SUMMARY (00:00 UTC - NOW):")
print(f"- Total 5-Minute Candles Audited:  {total_candles}")
print(f"- Candles Reaching 98¢/99¢:        {candles_98_plus} / {total_candles} ({(candles_98_plus/max(1,total_candles))*100:.1f}%)")
print(f"- Clean Wins from 98¢/99¢:         {clean_wins_from_98} / {max(1, candles_98_plus)} ({(clean_wins_from_98/max(1,candles_98_plus))*100:.1f}%)")
print(f"- Reversals after hitting 98¢/99¢: {reversals_from_98}")
print("="*95)
