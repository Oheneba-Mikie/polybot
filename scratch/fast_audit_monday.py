import requests
import json
import datetime
import time
import sys
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

now = int(time.time())
# Monday Aug 24, 2026 00:00:00 UTC
monday_start = int(datetime.datetime(2026, 8, 24, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp())

timestamps = list(range(monday_start, now - 300, 300))

def audit_candle(ts):
    slug = f"btc-updown-5m-{ts}"
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M UTC")
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
        if not r or not r[0].get("markets"):
            return None
            
        mkt = r[0]["markets"][0]
        outcome_prices_raw = mkt.get("outcomePrices", "[]")
        outcome_prices = json.loads(outcome_prices_raw) if isinstance(outcome_prices_raw, str) else outcome_prices_raw
        
        cid = mkt.get("conditionId")
        r_trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=100", timeout=3).json()
        
        max_up_px = 0.0
        max_dn_px = 0.0
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
        is_clean_win = False
        is_reversal = False
        
        if hit_98:
            token_hit = "UP" if max_up_px >= 0.98 else "DOWN"
            if token_hit == winner:
                is_clean_win = True
                status_str = "✅ WON (1.00)"
            else:
                is_reversal = True
                status_str = "❌ REVERSED (0.00)"
        else:
            status_str = f"⚪ Peak: ${peak_price:.2f}"
            
        return {
            "ts": ts,
            "time": dt_str,
            "slug": slug,
            "winner": winner,
            "max_up": max_up_px,
            "max_dn": max_dn_px,
            "peak": peak_price,
            "hit_98": hit_98,
            "is_clean_win": is_clean_win,
            "is_reversal": is_reversal,
            "status": status_str,
            "trades": len(r_trades)
        }
    except Exception:
        return None

print(f"Auditing {len(timestamps)} Monday candles in parallel...")
with ThreadPoolExecutor(max_workers=20) as executor:
    results = list(executor.map(audit_candle, timestamps))

records = sorted([r for r in results if r is not None], key=lambda x: x["ts"])

total_candles = len(records)
candles_98_plus = sum(1 for r in records if r["hit_98"])
clean_wins = sum(1 for r in records if r["is_clean_win"])
reversals = sum(1 for r in records if r["is_reversal"])

print("="*95)
print(f"📊 FULL MONDAY (AUG 24, 2026) 5-MINUTE BTC CANDLE AUDIT (00:00 UTC - NOW)")
print("="*95)
print(f"{'Candle Time':<12} | {'Winner':<6} | {'Peak UP Px':<11} | {'Peak DN Px':<11} | {'Overall Peak':<12} | {'98¢/99¢ Status':<18} | Trades")
print("-" * 95)
for rec in records[-30:]:
    print(f"{rec['time']:<12} | {rec['winner']:<6} | ${rec['max_up']:<10.3f} | ${rec['max_dn']:<10.3f} | ${rec['peak']:<11.3f} | {rec['status']:<18} | {rec['trades']}")

print("="*95)
print(f"📊 MONDAY AGGREGATE STATISTICAL SUMMARY (00:00 UTC - NOW):")
print(f"- Total 5-Minute Candles Audited:     {total_candles}")
print(f"- Candles Reaching 98¢/99¢:           {candles_98_plus} / {total_candles} ({(candles_98_plus/max(1,total_candles))*100:.1f}%)")
print(f"- Clean Wins from 98¢/99¢:            {clean_wins} / {max(1, candles_98_plus)} ({(clean_wins/max(1,candles_98_plus))*100:.1f}%)")
print(f"- Reversals after hitting 98¢/99¢:    {reversals}")
print("="*95)
