import requests
import json
import time

token = 'HzdjRAVU6q3VD8cQ7IbB8GQwQsvqD_uxeqjcy9cU4v_'
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
service_id = '92085ee6-62ab-463d-a313-cab77706a35c'

query_latest = """
query getService($id: String!) {
  service(id: $id) {
    id
    name
    deployments(first: 1) {
      edges {
        node {
          id
          status
          createdAt
        }
      }
    }
  }
}
"""

print("Waiting for deployment to complete...")
dep_id = None
for _ in range(20):
    res = requests.post(
        'https://backboard.railway.com/graphql/v2',
        json={'query': query_latest, 'variables': {'id': service_id}},
        headers=headers
    )
    edges = res.json().get('data', {}).get('service', {}).get('deployments', {}).get('edges', [])
    if edges:
        node = edges[0]['node']
        dep_id = node['id']
        status = node['status']
        print(f"Deployment {dep_id}: status={status}")
        if status == 'SUCCESS':
            break
        if status in ['FAILED', 'CRASHED']:
            print("Deployment failed/crashed, getting logs...")
            break
    time.sleep(5)

if dep_id:
    print(f"\n--- Logs for {dep_id} ---")
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
        json={'query': query_logs, 'variables': {'deploymentId': dep_id}},
        headers=headers
    )
    logs = res.json().get('data', {}).get('deploymentLogs', [])
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    for entry in logs[-40:]:
        print(f"[{entry.get('timestamp')}] {entry.get('message')}")
