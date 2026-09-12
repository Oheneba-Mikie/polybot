import subprocess
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 LOG AUDIT: WHY THE 10:45 AM TRADE HELD INTO EXPIRATION")
print("="*95)

# Let's inspect the transition timestamps:
# 1. Trade occurred at 14:46:16 UTC
# 2. Deployment was created at 14:45:45 UTC, container booted at 14:46:20 UTC

res = subprocess.run(
    'railway logs -s 812a5eb5-d070-4ede-8665-9bd7ba4c39e8 -p 68c99960-82ce-4e00-a23b-0cb28bf4d227 -e production -n 40',
    capture_output=True,
    text=True,
    shell=True,
    cwd="d:\\Desktop\\antigravity\\POLYBOT\\polybot\\scalper_bailout_deploy"
)

print(res.stdout)
print("="*95)
