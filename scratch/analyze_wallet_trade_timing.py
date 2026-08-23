import os
import sys
import json
import datetime
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("scalper_bailout_deploy/.env")

DATA_HOST = "https://data-api.polymarket.com"
POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS", "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8")

print("="*100)
print("🔍 AUDIT: EXACT HOLD TIMES (BUY -> SELL DURATION) FOR ALL REAL TRADES TODAY")
print("="*100)

r_act = requests.get(f"{DATA_HOST}/activity?user={POLYMARKET_ADDRESS}&limit=100", timeout=10).json()

today_acts = []
for a in r_act:
    ts = a.get("timestamp", 0)
    dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
    if dt.day == 22 and dt.month == 8 and dt.year == 2026:
        today_acts.append(a)

today_acts = sorted(today_acts, key=lambda x: x.get("timestamp", 0))

# Group by market
from collections import defaultdict
grouped = defaultdict(list)
for a in today_acts:
    title = a.get("title", "")
    grouped[title].append(a)

sold_trades = []
resolved_trades = []

for mkt_title, acts in grouped.items():
    buys = [a for a in acts if a.get("type") == "TRADE" and a.get("side") == "BUY"]
    sells = [a for a in acts if a.get("type") == "TRADE" and a.get("side") == "SELL"]
    redeems = [a for a in acts if a.get("type") == "REDEEM"]
    
    if buys and sells:
        b = buys[0]
        s = sells[0]
        b_ts = b.get("timestamp", 0)
        s_ts = s.get("timestamp", 0)
        duration = s_ts - b_ts
        b_dt = datetime.datetime.fromtimestamp(b_ts, datetime.timezone.utc).strftime("%H:%M:%S")
        s_dt = datetime.datetime.fromtimestamp(s_ts, datetime.timezone.utc).strftime("%H:%M:%S")
        b_px = float(b.get("price", 0))
        s_px = float(s.get("price", 0))
        shares = float(b.get("size", 0))
        profit = (s_px - b_px) * shares
        
        sold_trades.append({
            "market": mkt_title,
            "buy_time": b_dt,
            "sell_time": s_dt,
            "duration_sec": duration,
            "buy_px": b_px,
            "sell_px": s_px,
            "shares": shares,
            "profit": profit
        })
    elif buys and redeems:
        b = buys[0]
        r = redeems[0]
        b_ts = b.get("timestamp", 0)
        r_ts = r.get("timestamp", 0)
        b_dt = datetime.datetime.fromtimestamp(b_ts, datetime.timezone.utc).strftime("%H:%M:%S")
        duration = r_ts - b_ts
        b_px = float(b.get("price", 0))
        shares = float(b.get("size", 0))
        profit = (1.00 - b_px) * shares
        resolved_trades.append({
            "market": mkt_title,
            "buy_time": b_dt,
            "duration_to_resolve_sec": duration,
            "buy_px": b_px,
            "shares": shares,
            "profit": profit
        })

print(f"\n📊 1. SCALPED TRADES (BOUGHT AND SOLD AT MARKET BID): {len(sold_trades)} Trades")
print(f"{'#':<3} | {'BUY TIME':<9} | {'SELL TIME':<10} | {'HOLD TIME (SECONDS)':<20} | {'BUY PX':<7} | {'SELL PX':<8} | {'PROFIT'}")
print("="*80)

durations = []
for i, t in enumerate(sold_trades):
    durations.append(t["duration_sec"])
    print(f"{i+1:<3} | {t['buy_time']:<9} | {t['sell_time']:<10} | {t['duration_sec']} seconds{'':<11} | ${t['buy_px']:<6.2f} | ${t['sell_px']:<7.2f} | +${t['profit']:.4f}")

if durations:
    min_dur = min(durations)
    max_dur = max(durations)
    avg_dur = sum(durations) / len(durations)
    durations_sorted = sorted(durations)
    median_dur = durations_sorted[len(durations_sorted)//2]
    
    print("\n" + "="*80)
    print("📈 STATISTICAL SUMMARY OF LIVE HOLD TIMES TODAY:")
    print("="*80)
    print(f"⚡ FASTEST SELL (Minimum Time) : {min_dur} seconds")
    print(f"🐢 SLOWEST SELL (Maximum Time) : {max_dur} seconds")
    print(f"📊 AVERAGE HOLD TIME           : {avg_dur:.1f} seconds")
    print(f"🎯 MEDIAN HOLD TIME            : {median_dur} seconds")
    print(f"⏱️ 80% of all scalps sold in   : <= {durations_sorted[int(len(durations_sorted)*0.8)]} seconds")
    print("="*80)

print(f"\n🏛️ 2. TRADES HELD TO RESOLUTION ($1.00 PAYOUT): {len(resolved_trades)} Trades")
for i, t in enumerate(resolved_trades):
    print(f"  • {t['market'][:45]} | Buy Time: {t['buy_time']} | Held to $1.00 Payout (+${t['profit']:.4f})")

print("="*100)
