import requests
import json
import os

token = 'HzdjRAVU6q3VD8cQ7IbB8GQwQsvqD_uxeqjcy9cU4v_'
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

query = """
query getProject($id: String!) {
  project(id: $id) {
    id
    name
    environments {
      edges {
        node {
          id
          name
        }
      }
    }
    services {
      edges {
        node {
          id
          name
        }
      }
    }
  }
}
"""

res = requests.post(
    'https://backboard.railway.com/graphql/v2',
    json={'query': query, 'variables': {'id': '68c99960-82ce-4e00-a23b-0cb28bf4d227'}},
    headers=headers
)

print('Status:', res.status_code)
data = res.json()
print(json.dumps(data, indent=2))

with open('project_info.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
