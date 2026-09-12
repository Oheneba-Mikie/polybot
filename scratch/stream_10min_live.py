import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print(f"📡 10-MINUTE REAL-TIME RAILWAY LOG STREAM (STARTED AT {datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S UTC')})")
print("="*95)

seen_logs = set()

# Stream for 10 minutes (120 iterations of 5s)
for i in range(120):
    now = time.time()
    cur_w_s = int(now // 300) * 300
    cur_w_e = cur_w_s + 300
    time_left = cur_w_e - now
    slug = f"btc-updown-5m-{cur_w_s}"
    
    dt_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    
    try:
        r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=3).json()
        bal = r.get("balance")
        btc = r.get("chainlink_price")
        strike = r.get("strike_price")
        gap = r.get("strike_gap")
        trades = r.get("total_trades")
        profit = r.get("total_profit_usdc")
        
        # Print any new logs
        logs = r.get("logs", [])
        for l in logs:
            if l not in seen_logs:
                print(f"[NEW BOT LOG] {l}")
                seen_logs.add(l)
                
        if i % 6 == 0: # Every 30 seconds print heartbeat summary
            print(f"[{dt_str}] Candle: {slug} (T-{time_left:.0f}s) | Live BTC: ${btc if btc else 0:.2f} | Strike: ${strike if strike else 0:.2f} | Gap: ${gap if gap else 0:.1f} | Bal: ${bal} | Snipes: {trades} (+${profit:.2f})")
            
    except Exception as e:
        print(f"[{dt_str}] Connection error: {e}")
        
    time.sleep(5)

print("="*95)
