import requests
import json

TOKEN = "AVUuWViq8WgZYftM09_5WU-D0JUHOl3H0wAd5rf0zof"
API_URL = "https://backboard.railway.app/graphql/v2"
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# 1. Query projects
q = """
query {
  me {
    email
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

r = requests.post(API_URL, json={"query": q}, headers=headers).json()
print("Account:", r.get("data", {}).get("me", {}).get("email"))
projects = r.get("data", {}).get("me", {}).get("projects", {}).get("edges", [])
for p in projects:
    p_node = p["node"]
    print(f"Project: {p_node['name']} ({p_node['id']})")
    for s in p_node.get("services", {}).get("edges", []):
        print(f"  Service: {s['node']['name']} ({s['node']['id']})")
