import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

try:
    r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=6).json()
    print("="*80)
    print("🤖 RAILWAY LIVE BOT STATUS:")
    print("="*80)
    print(f"  • Bot Status:    {r.get('status')}")
    print(f"  • Current Phase: {r.get('phase')}")
    print(f"  • Live Balance:  {r.get('live_balance')}")
    print(f"  • Total Trades:  {r.get('total_trades')}")
    print(f"\n📋 Latest 5 Log Messages from Container:")
    for l in r.get('logs', [])[-5:]:
        print(f"    {l}")
    print("="*80)
except Exception as e:
    print("Could not reach Railway container:", e)
