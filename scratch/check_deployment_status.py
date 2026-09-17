import requests
import json
import time

token = 'HzdjRAVU6q3VD8cQ7IbB8GQwQsvqD_uxeqjcy9cU4v_'
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

deployment_id = '6f212c1a-c5bb-41ec-b968-901eaffafb17'

query = """
query getDeployment($id: String!) {
  deployment(id: $id) {
    id
    status
    environmentId
    serviceId
    createdAt
  }
}
"""

for _ in range(6):
    res = requests.post(
        'https://backboard.railway.com/graphql/v2',
        json={'query': query, 'variables': {'id': deployment_id}},
        headers=headers
    )
    data = res.json()
    status = data.get('data', {}).get('deployment', {}).get('status', 'UNKNOWN')
    print(f"Deployment status: {status}")
    if status in ['SUCCESS', 'CRASHED', 'FAILED']:
        break
    time.sleep(5)
