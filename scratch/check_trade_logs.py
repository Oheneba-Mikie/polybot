import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

try:
    r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=6).json()
    print("="*80)
    print("📋 RAILWAY BOT CONTAINER LOGS:")
    print("="*80)
    logs = r.get("logs", [])
    print(f"Total logs in memory: {len(logs)}")
    for l in logs[-30:]:
        print(f"  {l}")
    print("="*80)
except Exception as e:
    print("Error querying state:", e)
