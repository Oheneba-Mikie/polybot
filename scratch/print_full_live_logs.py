import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*105)
print("📜 FULL VERBATIM LOGS DIRECTLY FROM LIVE CONTAINER MEMORY")
print("="*105)

try:
    r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=5).json()
    logs = r.get("logs", [])
    print(f"Total Log Entries in Memory: {len(logs)}\n")
    for idx, l in enumerate(logs):
        print(f"{idx+1:>3}. {l}")
except Exception as e:
    print("Error fetching state logs:", e)

print("="*105)
