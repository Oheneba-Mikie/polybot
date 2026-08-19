import requests
import json

TOKEN = "ebTqQkcbaZEtqXRnGS2ZUx1AX5ayzx-2WaeMlywluvN"
PROJECT = "5d344874-8269-481c-8c41-efbb695ed599"
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
              }
            }
          }
        }
      }
    }
  }
}
"""

resp = requests.post(API_URL, headers=headers, json={"query": query})
data = resp.json()
print(json.dumps(data, indent=2))
