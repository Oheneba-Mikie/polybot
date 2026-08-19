import urllib.request
import json
import time

def audit_overnight():
    print("=== OVERNIGHT AUDIT (04:15 UTC to 08:10 UTC - 48 ROUNDS) ===")
    
    # Query Binance for past 48 5m candles
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=48"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        res = urllib.request.urlopen(req)
        candles = json.loads(res.read().decode('utf-8'))
        
        triggers = 0
        quiet_rounds = 0
        
        print("\n| Round # | Time (UTC) | Open Price | 5m High/Low Move | Market Condition |")
        print("| :--- | :--- | :--- | :--- | :--- |")
        
        for idx, c in enumerate(candles, 1):
            open_p = float(c[1])
            high_p = float(c[2])
            low_p = float(c[3])
            t_ms = c[0]
            
            t_str = time.strftime('%H:%M', time.gmtime(t_ms / 1000))
            max_move = max(abs(high_p - open_p), abs(low_p - open_p))
            
            if max_move >= 12.0:
                triggers += 1
                cond = f"TRIGGER! (+$12+ move = Pair Cost <= $0.98)"
            else:
                quiet_rounds += 1
                cond = f"Quiet Range-Bound (Move ${max_move:.2f} < $12 = Pair Cost $1.01+)"
                
            print(f"| #{idx:2d} | {t_str} GMT | ${open_p:,.2f} | ${max_move:+.2f} | {cond} |")
            
        print("\n=======================================================")
        print(f"OVERNIGHT SUMMARY (04:15 GMT to 08:10 GMT):")
        print(f"- Total 5m Rounds: {len(candles)}")
        print(f"- Quiet Range-Bound Rounds (Move < $12): {quiet_rounds} ({quiet_rounds/len(candles)*100:.1f}%)")
        print(f"- Volatility Trigger Rounds (Move >= $12): {triggers} ({triggers/len(candles)*100:.1f}%)")
        print("=======================================================")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    audit_overnight()
