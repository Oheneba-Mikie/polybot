import requests
import json

token = 'HzdjRAVU6q3VD8cQ7IbB8GQwQsvqD_uxeqjcy9cU4v_'
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
project_id = '68c99960-82ce-4e00-a23b-0cb28bf4d227'

query = """
query getProjectServices($id: String!) {
  project(id: $id) {
    id
    name
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
    json={'query': query, 'variables': {'id': project_id}},
    headers=headers
)

print(json.dumps(res.json(), indent=2))
