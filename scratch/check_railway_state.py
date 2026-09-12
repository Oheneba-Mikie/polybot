import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

try:
    r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=6).json()
    print("Railway Container State:")
    print(f"  Status:         {r.get('status')}")
    print(f"  Live Balance:   ${r.get('live_balance')}")
    print(f"  Active Phase:   {r.get('phase')}")
    print(f"  Recent Logs ({len(r.get('logs', []))} entries):")
    for l in r.get('logs', [])[-5:]:
        print(f"    {l}")
except Exception as e:
    print("Railway state query error:", e)
