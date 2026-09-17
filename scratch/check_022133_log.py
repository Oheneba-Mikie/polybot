import requests
r = requests.get('https://polybot-sniper-mikie.fly.dev/api/state').json()
logs = r.get('logs', [])
target_logs = [l for l in logs if '02:21:' in l]
with open('scratch/target_logs_0221.txt', 'w', encoding='utf-8') as f:
    for l in target_logs:
        f.write(l + '\n')
print(f'Found {len(target_logs)} logs for 02:21')
