import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*115)
print("🔍 24-HOUR POLYMARKET ORDER BOOK & BUYER AVAILABILITY AUDIT DURING SURGES")
print("="*115)

# Query recent trades on 5m BTC markets from Polymarket Data API
try:
    r_trades = requests.get("https://data-api.polymarket.com/trades?limit=500").json()
    btc_trades = [t for t in r_trades if "Bitcoin Up or Down" in t.get("title", "")]
    print(f"Found {len(btc_trades)} recent trades on Polymarket 5-minute markets.\n")
    
    # Group trades by 5m market title
    markets_trades = {}
    for t in btc_trades:
        title = t.get("title")
        if title not in markets_trades:
            markets_trades[title] = []
        markets_trades[title].append(t)
        
    print(f"Auditing buyer activity across {len(markets_trades)} 5-minute markets:\n")
    
    for title, tr_list in list(markets_trades.items())[:12]:
        # Sort chronologically
        sorted_tr = sorted(tr_list, key=lambda x: x.get("timestamp", 0))
        
        # Analyze price trajectory of the surge outcome
        outcomes_seen = set(t.get("outcome") for t in sorted_tr)
        
        for out in outcomes_seen:
            out_trades = [t for t in sorted_tr if t.get("outcome") == out]
            if len(out_trades) >= 3:
                prices = [float(t.get("price", 0)) for t in out_trades]
                times = [t.get("timestamp", 0) for t in out_trades]
                min_px = min(prices)
                max_px = max(prices)
                first_px = prices[0]
                last_px = prices[-1]
                
                # Check if buyers paid higher prices after the initial wave
                higher_buys = [t for t in out_trades if float(t.get("price", 0)) >= (first_px + 0.03) and t.get("side") == "BUY"]
                total_volume_higher = sum(float(t.get("size", 0)) for t in higher_buys)
                
                print(f"🎯 Market: {title} | Outcome: {out:<4}")
                print(f"   • Surge Entry Price: ${first_px:.3f} -> Peak Buyer Price: ${max_px:.3f} (Max Gain: +${max_px - first_px:.3f})")
                print(f"   • Were Higher Buyers Available? {'YES! (' + str(len(higher_buys)) + ' buyers paying higher)' if higher_buys else 'NO (Thin Book)'}")
                if higher_buys:
                    print(f"   • Total Shares Absorbed by Higher Buyers: {total_volume_higher:.1f} shares @ ${higher_buys[0].get('price'):.3f}+")
                print("-" * 115)
                
except Exception as e:
    print("Audit Error:", e)

print("="*115)
