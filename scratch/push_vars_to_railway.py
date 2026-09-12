import os
import subprocess
import sys
from dotenv import dotenv_values

sys.stdout.reconfigure(encoding='utf-8')

env_vars = dotenv_values("scalper_bailout_deploy/.env")

print("="*80)
print("🚀 PUSHING ENVIRONMENT VARIABLES TO RAILWAY VIA CLI...")
print("="*80)

for k, v in env_vars.items():
    if not k or not v: continue
    print(f"Setting {k}...")
    res = subprocess.run(
        f'railway variable set "{k}={v}" -p 68c99960-82ce-4e00-a23b-0cb28bf4d227 -e production -s 812a5eb5-d070-4ede-8665-9bd7ba4c39e8',
        cwd="d:\\Desktop\\antigravity\\POLYBOT\\polybot\\scalper_bailout_deploy",
        capture_output=True,
        text=True,
        shell=True
    )
    if res.returncode == 0:
        print(f"  ✅ {k} set successfully.")
    else:
        print(f"  ❌ Error setting {k}: {res.stderr}")

print("\n" + "="*80)
print("🎉 ALL NEW KEYS PUSHED TO RAILWAY!")
print("="*80)
