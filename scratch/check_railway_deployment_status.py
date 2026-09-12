import subprocess
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*80)
print("🔍 RAILWAY DEPLOYMENT AUDIT: CHECKING ACTIVE DEPLOYMENT & COMMIT ON CLOUD")
print("="*80)

res = subprocess.run(
    'railway deployment list -s 812a5eb5-d070-4ede-8665-9bd7ba4c39e8 -p 68c99960-82ce-4e00-a23b-0cb28bf4d227 -e production --json',
    capture_output=True,
    text=True,
    shell=True,
    cwd="d:\\Desktop\\antigravity\\POLYBOT\\polybot\\scalper_bailout_deploy"
)

if res.returncode == 0:
    try:
        data = json.loads(res.stdout)
        print(f"Total Deployments Listed: {len(data)}")
        for d in data[:5]:
            dep_id = d.get("id", "N/A")
            status = d.get("status", "N/A")
            created = d.get("createdAt", "N/A")
            meta = d.get("meta", {})
            commit_msg = meta.get("commitMessage", "N/A")
            commit_hash = meta.get("commitHash", "N/A")[:8]
            print(f"  • Status: {status:<10} | Created: {created} | Commit: [{commit_hash}] {commit_msg}")
    except Exception as e:
        print("Raw output:", res.stdout[:500])
else:
    print("Error querying deployments:", res.stderr)

print("="*80)
