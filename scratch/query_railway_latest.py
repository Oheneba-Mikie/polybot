import requests
import json
import os

token = "84e59043-4ce4-436f-871d-5573de029199"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

query = """
query {
  deployments(input: { projectId: "68c99960-82ce-4e00-a23b-0cb28bf4d227", serviceId: "812a5eb5-d070-4ede-8665-9bd7ba4c39e8" }, first: 5) {
    edges {
      node {
        id
        status
        createdAt
        updatedAt
      }
    }
  }
}
"""

r = requests.post("https://backboard.railway.com/graphql/v2", json={"query": query}, headers=headers).json()
print(json.dumps(r, indent=2))
