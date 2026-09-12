import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("📡 LIVE RAILWAY MONITORING STREAM: OBSERVING NEXT CANDLE FLOW")
print("="*95)

seen_logs = set()
end_time = time.time() + 45

while time.time() < end_time:
    try:
        r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=3).json()
        
        cur_candle = r.get("current_candle", "N/A")
        strike = r.get("strike_price", 0)
        btc = r.get("chainlink_price", 0)
        gap = r.get("gap", 0)
        bal = r.get("balance_usdc", 0)
        phase = r.get("phase", "N/A")
        
        new_logs = []
        for l in r.get("logs", []):
            if l not in seen_logs:
                new_logs.append(l)
                seen_logs.add(l)
                
        if new_logs:
            for nl in new_logs:
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {nl}")
        else:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Candle: {cur_candle} | BTC: ${btc:.2f} | Strike: ${strike:.2f} | Gap: ${gap:.2f} | Bal: ${bal} | Phase: {phase}")
            
    except Exception as e:
        print(f"Stream note: {e}")
        
    time.sleep(5)

print("="*95)
