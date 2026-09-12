import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*105)
print("🔍 HONEST EMPIRICAL AUDIT: RECENT CANDLE GAPS & WHY ASKS/GAPS QUALIFY OR SKIP")
print("="*105)

# 1. Audit last 12 5-minute candles (past 1 hour) using Kraken OHLC
url = "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=5"
try:
    r = requests.get(url, timeout=5).json()
    candles = r.get("result", {}).get("XXBTZUSD", [])[-12:]
    
    print(f"Auditing last {len(candles)} 5-minute Bitcoin candles (Past 1 Hour):\n")
    print(f"{'Time (UTC)':<18} | {'Strike (Open)':<15} | {'Close Price':<15} | {'Gap ($)':<12} | {'Qualifies Rule 1 (>= $15)?'}")
    print("-" * 85)
    
    qualified_cnt = 0
    small_gap_cnt = 0
    
    for c in candles:
        t = int(c[0])
        t_str = time.strftime("%H:%M UTC", time.gmtime(t))
        o = float(c[1])
        cl = float(c[4])
        gap = cl - o
        abs_gap = abs(gap)
        
        qual = "✅ YES (Gap >= $15)" if abs_gap >= 15.0 else "❌ NO (Chop/Small Gap)"
        if abs_gap >= 15.0:
            qualified_cnt += 1
        else:
            small_gap_cnt += 1
            
        print(f"{t_str:<18} | ${o:<14.2f} | ${cl:<14.2f} | ${abs_gap:<11.2f} | {qual}")
        
    print("\n" + "="*85)
    print(f"📊 PAST 1-HOUR REALITY:")
    print(f"  • Total Candles:                 {len(candles)}")
    print(f"  • Candles that Skipped (< $15):  {small_gap_cnt} candles (Tight market consolidation / chop)")
    print(f"  • Candles with Gap >= $15:       {qualified_cnt} candles")
    print("="*85)

except Exception as e:
    print("Error:", e)

# 2. Check full 7-day distribution of Gaps ($5, $8, $10, $15)
try:
    all_c = r.get("result", {}).get("XXBTZUSD", [])[-720:] # Last ~2.5 days
    print(f"\n📊 720 CANDLE DISTRIBUTION (~60 HOURS):")
    gap_5_cnt = sum(1 for c in all_c if abs(float(c[4]) - float(c[1])) >= 5.0)
    gap_8_cnt = sum(1 for c in all_c if abs(float(c[4]) - float(c[1])) >= 8.0)
    gap_10_cnt = sum(1 for c in all_c if abs(float(c[4]) - float(c[1])) >= 10.0)
    gap_15_cnt = sum(1 for c in all_c if abs(float(c[4]) - float(c[1])) >= 15.0)
    
    print(f"  • Candles with Gap >= $5.00:   {gap_5_cnt} / {len(all_c)} ({(gap_5_cnt/len(all_c)*100):.1f}%)")
    print(f"  • Candles with Gap >= $8.00:   {gap_8_cnt} / {len(all_c)} ({(gap_8_cnt/len(all_c)*100):.1f}%)")
    print(f"  • Candles with Gap >= $10.00:  {gap_10_cnt} / {len(all_c)} ({(gap_10_cnt/len(all_c)*100):.1f}%)")
    print(f"  • Candles with Gap >= $15.00:  {gap_15_cnt} / {len(all_c)} ({(gap_15_cnt/len(all_c)*100):.1f}%)")
except Exception as e:
    pass

print("="*105)
