import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

print("="*95)
print(f"📡 REAL-TIME LIVE MONITORING STREAM (STARTED AT {datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S UTC')})")
print("="*95)

for i in range(12): # Monitor for ~60s
    now = time.time()
    cur_w_s = int(now // 300) * 300
    cur_w_e = cur_w_s + 300
    time_left = cur_w_e - now
    slug = f"btc-updown-5m-{cur_w_s}"
    
    dt_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    
    # Query Railway State
    try:
        r_state = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=2).json()
        bal = r_state.get("balance")
        btc = r_state.get("chainlink_price")
        trades = r_state.get("total_trades")
        profit = r_state.get("total_profit_usdc")
        last_log = r_state.get("logs", [""])[-1] if r_state.get("logs") else ""
        print(f"[{dt_str}] T-{time_left:.1f}s | BTC: ${btc if btc else 0:.2f} | Bal: ${bal} | Snipes: {trades} (+${profit:.2f}) | Log: {last_log}")
    except Exception as e:
        print(f"[{dt_str}] Error: {e}")
        
    time.sleep(5)

print("="*95)
