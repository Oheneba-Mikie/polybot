import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

res = subprocess.run(["git", "log", "--all", "--full-history", "--", "*.env*"], capture_output=True, text=True, cwd="d:\\Desktop\\antigravity\\POLYBOT\\polybot")
print("="*80)
print("🔍 CHECKING IF ANY .env FILE WAS EVER COMMITTED TO GIT:")
print("="*80)
if res.stdout.strip():
    print("Found .env commits in history:")
    print(res.stdout)
else:
    print("✅ ZERO .env files were ever committed in git history.")
print("="*80)
