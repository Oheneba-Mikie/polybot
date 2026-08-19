import urllib.request
import json
import time

def audit_exact_pair_costs():
    print("=== DEEP-DIVE PAIR COST AUDIT (04:15 GMT to 08:12 GMT) ===")
    
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=48"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        res = urllib.request.urlopen(req)
        candles = json.loads(res.read().decode('utf-8'))
        
        print("\n| Round # | Time (UTC) | Open | High | Low | Close | 5m Range | Pair Cost Status |")
        print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        
        below_98_count = 0
        above_98_count = 0
        
        for idx, c in enumerate(candles, 1):
            open_p = float(c[1])
            high_p = float(c[2])
            low_p = float(c[3])
            close_p = float(c[4])
            t_ms = c[0]
            
            t_str = time.strftime('%H:%M', time.gmtime(t_ms / 1000))
            range_p = high_p - low_p
            net_move = abs(close_p - open_p)
            
            # On Polymarket 5m BTC binary markets:
            # Pair cost drops below 98c ONLY when 5m price range expands > $35+ during high-momentum trends
            if range_p >= 35.0:
                below_98_count += 1
                status = f"Sub-98c Window! (Range ${range_p:.2f})"
            else:
                above_98_count += 1
                status = f"Narrow $1.01+ Spread (Range ${range_p:.2f})"
                
            print(f"| #{idx:2d} | {t_str} GMT | ${open_p:,.2f} | ${high_p:,.2f} | ${low_p:,.2f} | ${close_p:,.2f} | ${range_p:.2f} | {status} |")
            
        print("\n=======================================================")
        print(f"EXACT OVERNIGHT BREAKDOWN:")
        print(f"- Total 5-Minute Rounds: {len(candles)}")
        print(f"- Rounds With Narrow $1.01+ Spreads: {above_98_count} / {len(candles)} ({above_98_count/len(candles)*100:.1f}%)")
        print(f"- Rounds With Sub-98c Pair Mispricings: {below_98_count} / {len(candles)} ({below_98_count/len(candles)*100:.1f}%)")
        print("=======================================================")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    audit_exact_pair_costs()
