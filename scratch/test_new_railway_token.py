import requests
import subprocess
import os

TOKEN = "525ef0fa-717d-43a2-a4ba-d5df02a8dee4"
API_URL = "https://backboard.railway.app/graphql/v2"

print("1. Testing GraphQL with Token...")
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
try:
    r = requests.post(API_URL, json={"query": "query { me { email } }"}, headers=headers, timeout=5)
    print("GraphQL Status:", r.status_code)
    print("GraphQL Response:", r.text)
except Exception as e:
    print("GraphQL Error:", e)

print("\n2. Testing Railway CLI with Token...")
env = os.environ.copy()
env["RAILWAY_TOKEN"] = TOKEN
try:
    res = subprocess.run(["railway", "whoami"], env=env, capture_output=True, text=True, timeout=10)
    print("CLI whoami return code:", res.returncode)
    print("CLI stdout:", res.stdout)
    print("CLI stderr:", res.stderr)
except Exception as e:
    print("CLI Error:", e)
