import os
import sys
import json
import time
import datetime
import requests
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST = "https://data-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"

print("="*100)
print("🔎 2-HOUR REAL DATA QUERY: ANALYZING EVERY TRADE ON POLYMARKET BTC 5-MIN MARKETS")
print("="*100)

now = time.time()
current_w_s = int(now // 300) * 300

# Generate all 5-minute candle timestamps for the last 2 hours (24 candles)
num_candles = 24
candles = [current_w_s - (i * 300) for i in range(num_candles)]
candles.reverse()

print(f"Generated {len(candles)} candle windows across the past 2 hours.")

all_candle_data = []

price_buckets = {
    "0.01 - 0.05 (Deep Underdog)": {"count": 0, "volume_usd": 0.0, "shares": 0.0},
    "0.06 - 0.15 (Underdog)":      {"count": 0, "volume_usd": 0.0, "shares": 0.0},
    "0.16 - 0.35 (Low Probability)": {"count": 0, "volume_usd": 0.0, "shares": 0.0},
    "0.36 - 0.65 (50/50 Mid Battle)": {"count": 0, "volume_usd": 0.0, "shares": 0.0},
    "0.66 - 0.85 (Likely Favorite)":  {"count": 0, "volume_usd": 0.0, "shares": 0.0},
    "0.86 - 0.95 (Heavy Favorite)":   {"count": 0, "volume_usd": 0.0, "shares": 0.0},
    "0.96 - 0.99 (Ultra Squeeze)":    {"count": 0, "volume_usd": 0.0, "shares": 0.0},
}

all_trades_list = []

for idx, ts in enumerate(candles, 1):
    slug = f"btc-updown-5m-{ts}"
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M UTC")
    
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
        if not r or not r[0].get("markets"):
            continue
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        title = mkt.get("question", slug)
        
        # Get outcome prices/winner
        pxs = json.loads(mkt.get("outcomePrices") or "[]")
        winner = "OPEN"
        if pxs:
            if float(pxs[0]) >= 0.99: winner = "UP"
            elif float(pxs[1]) >= 0.99: winner = "DOWN"

        # Fetch all trades for this market
        r_t = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=500", timeout=5).json()
        trades = r_t if r_t else []
        
        up_trades = [t for t in trades if str(t.get("outcome")).lower() in ("up", "yes")]
        dn_trades = [t for t in trades if str(t.get("outcome")).lower() in ("down", "no")]
        
        total_vol = sum(float(t.get("usdcSize", 0) or (float(t.get("price", 0)) * float(t.get("size", 0)))) for t in trades)
        total_sh = sum(float(t.get("size", 0)) for t in trades)
        
        # Categorize price fills
        for t in trades:
            p = float(t.get("price") or 0)
            sz = float(t.get("size") or 0)
            usd = p * sz
            all_trades_list.append(t)
            
            if 0.01 <= p <= 0.05:
                b = price_buckets["0.01 - 0.05 (Deep Underdog)"]
            elif 0.05 < p <= 0.15:
                b = price_buckets["0.06 - 0.15 (Underdog)"]
            elif 0.15 < p <= 0.35:
                b = price_buckets["0.16 - 0.35 (Low Probability)"]
            elif 0.35 < p <= 0.65:
                b = price_buckets["0.36 - 0.65 (50/50 Mid Battle)"]
            elif 0.65 < p <= 0.85:
                b = price_buckets["0.66 - 0.85 (Likely Favorite)"]
            elif 0.85 < p <= 0.95:
                b = price_buckets["0.86 - 0.95 (Heavy Favorite)"]
            elif 0.95 < p <= 0.99:
                b = price_buckets["0.96 - 0.99 (Ultra Squeeze)"]
            else:
                continue
            b["count"] += 1
            b["shares"] += sz
            b["volume_usd"] += usd

        all_candle_data.append({
            "candle": dt_str,
            "slug": slug,
            "title": title,
            "winner": winner,
            "total_trades": len(trades),
            "up_trades": len(up_trades),
            "down_trades": len(dn_trades),
            "total_shares": round(total_sh, 1),
            "volume_usd": round(total_vol, 2),
            "raw_trades": trades
        })

    except Exception as e:
        continue

print("="*100)
print(f"{'CANDLE (UTC)':<14} | {'WINNER':<7} | {'TRADES':<8} | {'UP TRADES':<10} | {'DN TRADES':<10} | {'VOLUME ($)':<12} | {'TOTAL SHARES'}")
print("="*100)

for c in all_candle_data:
    print(f"{c['candle']:<14} | {c['winner']:<7} | {c['total_trades']:<8} | {c['up_trades']:<10} | {c['down_trades']:<10} | ${c['volume_usd']:<11.2f} | {c['total_shares']:.1f} sh")

print("\n" + "="*100)
print("📊 REAL FILL PRICE DISTRIBUTION ACROSS THE LAST 2 HOURS (WHERE TRADES ACTUALLY OCCUR)")
print("="*100)
print(f"{'PRICE RANGE / MARKET STATE':<32} | {'FILL COUNT':<12} | {'TOTAL SHARES':<15} | {'TOTAL VOLUME ($)':<16} | {'% OF TOTAL TRADES'}")
print("-"*100)

total_fills = len(all_trades_list)
for name, data in price_buckets.items():
    pct = (data['count'] / total_fills * 100) if total_fills > 0 else 0
    print(f"{name:<32} | {data['count']:<12} | {data['shares']:<15.1f} | ${data['volume_usd']:<15.2f} | {pct:.1f}%")

print("="*100)
print(f"Total Transactions Analyzed: {total_fills}")

with open("scratch/past_2hours_real_trade_distribution.json", "w") as fp:
    json.dump({
        "total_candles": len(all_candle_data),
        "total_trades": total_fills,
        "distribution": price_buckets,
        "candles": all_candle_data
    }, fp, indent=2)
