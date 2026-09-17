import requests
import json
import time

token = 'HzdjRAVU6q3VD8cQ7IbB8GQwQsvqD_uxeqjcy9cU4v_'
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

deployment_id = '6f212c1a-c5bb-41ec-b968-901eaffafb17'

query_logs = """
query getLogs($deploymentId: String!) {
  deploymentLogs(deploymentId: $deploymentId, limit: 100) {
    message
    timestamp
  }
}
"""

res = requests.post(
    'https://backboard.railway.com/graphql/v2',
    json={'query': query_logs, 'variables': {'deploymentId': deployment_id}},
    headers=headers
)

logs = res.json().get('data', {}).get('deploymentLogs', [])
print(f"Fetched {len(logs)} log entries:")
for entry in logs[-30:]:
    print(f"[{entry.get('timestamp')}] {entry.get('message')}")
