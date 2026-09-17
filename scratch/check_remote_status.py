import urllib.request
import json
import sys

try:
    req = urllib.request.urlopen("https://polybot-sniper-mikie.fly.dev/api/state", timeout=5)
    data = json.loads(req.read().decode("utf-8"))
    with open("scratch/remote_state.txt", "w", encoding="utf-8") as f:
        f.write(f"Status: {data.get('status')}\n")
        f.write(f"Completed: {data.get('completed_pairs_count')}\n")
        f.write("Recent Logs:\n")
        for log in data.get("logs", [])[-20:]:
            f.write(log + "\n")
    print("State dumped to scratch/remote_state.txt")
except Exception as e:
    print("Error:", e)
