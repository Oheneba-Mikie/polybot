import subprocess
import os

deploy_dir = r"d:\Desktop\antigravity\POLYBOT\polybot\batch_fok_deploy"

print("Running railway status...")
res = subprocess.run(["railway", "status"], cwd=deploy_dir, capture_output=True, text=True, shell=True)
print("STATUS STDOUT:\n", res.stdout)
print("STATUS STDERR:\n", res.stderr)
print("STATUS CODE:", res.returncode)

print("\nRunning railway up --detach...")
res2 = subprocess.run(["railway", "up", "--detach"], cwd=deploy_dir, capture_output=True, text=True, shell=True)
print("UP STDOUT:\n", res2.stdout)
print("UP STDERR:\n", res2.stderr)
print("UP CODE:", res2.returncode)
