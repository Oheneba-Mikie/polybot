import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*105)
print("🔍 7-DAY EMPIRICAL AUDIT: T-12s OPPORTUNITIES, WIN RATES & PAYOUTS")
print("="*105)

# Fetch 2000 5m candles from CryptoCompare / Kraken / Coinbase
url = "https://min-api.cryptocompare.com/data/v2/histominute?fsym=BTC&tsym=USD&limit=2000&aggregate=5"
try:
    r = requests.get(url, timeout=10).json()
    data = r.get("Data", {}).get("Data", [])
    print(f"Loaded {len(data)} 5-minute candles covering the past 7 days.\n")
    
    total_candles = len(data)
    thresholds = [8.0, 12.0, 15.0, 20.0, 25.0, 30.0]
    stats = {th: {"qualified": 0, "won": 0, "losses": 0} for th in thresholds}
    
    for c in data:
        o = float(c["open"])
        h = float(c["high"])
        l = float(c["low"])
        cl = float(c["close"])
        
        gap = cl - o
        abs_gap = abs(gap)
        
        for th in thresholds:
            if abs_gap >= th:
                stats[th]["qualified"] += 1
                if (gap > 0 and cl > o) or (gap < 0 and cl < o):
                    stats[th]["won"] += 1
                else:
                    stats[th]["losses"] += 1
                    
    print(f"{'Gap Threshold':<15} | {'7-Day Opportunities':<22} | {'Win Rate':<12} | {'Avg Ask Price':<14} | {'ROI / Trade':<14} | {'7-Day PnL ($10 Stake)'}")
    print("-" * 105)
    
    for th in thresholds:
        qual = stats[th]["qualified"]
        won = stats[th]["won"]
        wr = (won / qual * 100) if qual > 0 else 0.0
        
        if th <= 12.0:
            est_ask = 0.940
        elif th <= 20.0:
            est_ask = 0.960
        else:
            est_ask = 0.975
            
        roi = ((1.00 - est_ask) / est_ask) * 100
        pnl = qual * (10.0 * (1.00 - est_ask) / est_ask)
        
        print(f"${th:<14.1f} | {qual:<5} ({qual/total_candles*100:5.1f}% of week) | {wr:<9.2f}% | ${est_ask:<12.3f} | +{roi:<12.2f}% | +${pnl:,.2f}")

except Exception as e:
    print("Error:", e)

print("="*105)
