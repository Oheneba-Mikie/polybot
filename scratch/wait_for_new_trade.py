import requests, time, sys, json

sys.stdout.reconfigure(encoding='utf-8')

API_URL = "https://polybot-sniper-mikie.fly.dev/api/state"
ACTIVITY_URL = "https://data-api.polymarket.com/activity?user=0x81ad69942a32f7b1df4d16f0c3f79311f55de50a&limit=5"

# Initial state
init_trades = 0
init_activity_ts = 0

try:
    r = requests.get(API_URL, timeout=5).json()
    init_trades = len(r.get("recent_trades", []))
except Exception:
    pass

try:
    act = requests.get(ACTIVITY_URL, timeout=5).json()
    if act and isinstance(act, list):
        init_activity_ts = act[0].get("timestamp", 0)
except Exception:
    pass

print(f"Waiting for new trade... (Baseline trades: {init_trades}, Activity TS: {init_activity_ts})", flush=True)

start_time = time.time()
max_duration = 3600 # 1 hour max

while time.time() - start_time < max_duration:
    try:
        r = requests.get(API_URL, timeout=4).json()
        current_trades = r.get("recent_trades", [])
        
        # Check if new trade in bot state
        if len(current_trades) > init_trades:
            print("\n🚨 [NEW TRADE DETECTED IN BOT STATE] 🚨", flush=True)
            print(json.dumps(current_trades[0], indent=2), flush=True)
            # Print latest logs
            print("\nRecent Logs:", flush=True)
            for l in r.get("logs", [])[-6:]:
                print(l, flush=True)
            sys.exit(0)
            
        # Also check on-chain activity API directly
        act = requests.get(ACTIVITY_URL, timeout=4).json()
        if act and isinstance(act, list) and len(act) > 0:
            latest_ts = act[0].get("timestamp", 0)
            if latest_ts > init_activity_ts and act[0].get("type") == "TRADE":
                print("\n🚨 [NEW ON-CHAIN TRADE DETECTED] 🚨", flush=True)
                print(json.dumps(act[0], indent=2), flush=True)
                sys.exit(0)
                
    except Exception:
        pass
        
    time.sleep(3)

print("Timeout reached without new trade.", flush=True)
