import requests
import json

TOKEN = "ebTqQkcbaZEtqXRnGS2ZUx1AX5ayzx-2WaeMlywluvN"
API_URL = "https://backboard.railway.app/graphql/v2"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

query = """
query {
  me {
    projects {
      edges {
        node {
          id
          name
          services {
            edges {
              node {
                id
                name
                serviceInstances {
                  edges {
                    node {
                      id
                      environmentId
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

resp = requests.post(API_URL, headers=headers, json={"query": query}, timeout=15)
data = resp.json()
print(json.dumps(data, indent=2))
