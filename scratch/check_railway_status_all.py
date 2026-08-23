import subprocess
import json

out = subprocess.check_output(["railway", "service"], text=True)
print("="*80)
print("RAILWAY CURRENT SERVICE:")
print(out)
print("="*80)

# Check all deployments across projects
try:
    status_out = subprocess.check_output(["railway", "status"], text=True)
    print("RAILWAY STATUS:")
    print(status_out)
except Exception as e:
    print(e)
