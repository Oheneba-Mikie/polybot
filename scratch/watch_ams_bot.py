import requests, time, sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://polybot-sniper-mikie.fly.dev/api/state"
print("Monitoring live bot status and logs...")

seen_logs = set()
for _ in range(30):
    try:
        r = requests.get(url, timeout=4).json()
        status = r.get("status")
        persisted = r.get("cross_persisted_s", 0)
        logs = r.get("logs", [])
        for l in logs[-10:]:
            if l not in seen_logs:
                print(l)
                seen_logs.add(l)
    except Exception as e:
        pass
    time.sleep(1.5)
