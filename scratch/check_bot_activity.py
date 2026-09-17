import requests, json, sys

sys.stdout.reconfigure(encoding='utf-8')

try:
    r = requests.get('https://polybot-sniper-mikie.fly.dev/api/state', timeout=15).json()
    print("=== RECENT TRADES ===")
    print(json.dumps(r.get('recent_trades', []), indent=2))
    print("\n=== LOGS MATCHING SNIPE / BATCH / ERROR ===")
    for line in r.get('logs', []):
        if any(k in line for k in ['TRIGGERING', 'BATCH', 'CRITERIA', 'ERROR', 'SNIPE', 'FILLED']):
            print(line)
except Exception as e:
    print(f"Error: {e}")
