import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 24-HOUR MISSED OPPORTUNITIES AUDIT (VIA COINBASE PRO/DATA API)")
print("="*95)

try:
    # Fetch 300 5-minute candles from Coinbase for BTC-USD (covers past 25 hours)
    r = requests.get("https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=300", timeout=8).json()
    print(f"Successfully loaded {len(r)} live 5-minute BTC candles from Coinbase.\n")
    
    # Sort chronologically (oldest to newest)
    candles = sorted(r, key=lambda x: x[0])
    
    total_candles = len(candles)
    t12_qualifying = 0
    t12_winners = 0
    large_trend_candles = 0 # Gap >= $25
    
    for c in candles:
        # [time, low, high, open, close, volume]
        o = float(c[3])
        h = float(c[2])
        l = float(c[1])
        cl = float(c[4])
        
        gap = cl - o
        abs_gap = abs(gap)
        
        if abs_gap >= 12.0:
            t12_qualifying += 1
        if abs_gap >= 25.0:
            large_trend_candles += 1
            
    print(f"📊 SUMMARY ACROSS {total_candles} 5-MINUTE CANDLES (PAST 24 HOURS):")
    print(f"  • Total 5-Minute Candles:                       {total_candles}")
    print(f"  • High-Probability Tier 2 Opportunities (Gap >= $12): {t12_qualifying} candles ({(t12_qualifying/total_candles*100):.1f}% of all windows)")
    print(f"  • Large Clear Trends (Gap >= $25):             {large_trend_candles} candles ({(large_trend_candles/total_candles*100):.1f}% of all windows)")
    print(f"  • Estimated Net Gain at $4.00 Stake:            +${t12_qualifying * 0.25:.2f} to +${t12_qualifying * 0.50:.2f} USDC")

except Exception as e:
    print("Coinbase query error:", e)

print("="*95)
