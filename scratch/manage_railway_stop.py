import subprocess
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

print("="*80)
print("🛑 CHECKING & STOPPING RAILWAY SERVICES")
print("="*80)

# Check railway status / list
try:
    res = subprocess.run(["railway", "status"], capture_output=True, text=True, timeout=10)
    print("Railway Status Output:")
    print(res.stdout)
    if res.stderr:
        print("Stderr:", res.stderr)
except Exception as e:
    print("Error running railway status:", e)

# Also check down / stop
try:
    res_down = subprocess.run(["railway", "down", "-y"], capture_output=True, text=True, timeout=10)
    print("Railway Down Output:")
    print(res_down.stdout)
    if res_down.stderr:
        print("Stderr:", res_down.stderr)
except Exception as e:
    print("Error running railway down:", e)
