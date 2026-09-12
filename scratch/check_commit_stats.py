import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

for c in ["fd47aaf5", "e2d03271", "0437b2c1"]:
    res = subprocess.run(["git", "show", "--stat", c], capture_output=True, text=True, cwd="d:\\Desktop\\antigravity\\POLYBOT\\polybot")
    print(f"\n--- COMMIT {c} STATS ---")
    print(res.stdout[:1500])
