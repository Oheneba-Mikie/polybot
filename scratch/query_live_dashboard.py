import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://polybot-97-scalper-production.up.railway.app/api/state"

try:
    r = requests.get(url, timeout=5)
    print("="*80)
    print("📡 LIVE CLOUD BOT STATE (FROM RAILWAY DASHBOARD):")
    print("="*80)
    print(json.dumps(r.json(), indent=2))
    print("="*80)
except Exception as e:
    print(f"Error connecting to Railway dashboard: {e}")
