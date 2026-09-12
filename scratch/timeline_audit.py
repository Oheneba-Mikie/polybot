import subprocess, json, datetime, sys

sys.stdout.reconfigure(encoding='utf-8')

print('='*90)
print('⏱️ RAILWAY DEPLOYMENTS VS. ON-CHAIN TRADES TIMELINE CORRELATION')
print('='*90)

# 1. Fetch Railway Deployments
res = subprocess.run(
    'railway deployment list -s 812a5eb5-d070-4ede-8665-9bd7ba4c39e8 -p 68c99960-82ce-4e00-a23b-0cb28bf4d227 -e production --json',
    capture_output=True, text=True, shell=True, cwd='d:\\Desktop\\antigravity\\POLYBOT\\polybot\\scalper_bailout_deploy'
)

deps = []
if res.returncode == 0:
    deps = json.loads(res.stdout)
    print('📦 RAILWAY DEPLOYMENT HISTORY:')
    for d in deps[:10]:
        created = d.get('createdAt')
        status = d.get('status')
        dep_id = d.get('id')
        print(f'   • [{created}] Status: {status:<10} | ID: {dep_id}')

print('-'*90)
print('📊 COMPARISON WITH TODAY\'S TRADES:')
print('-'*90)
