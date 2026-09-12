import requests
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

TOKEN = "AVUuWViq8WgZYftM09_5WU-D0JUHOl3H0wAd5rf0zof"
API_URL = "https://backboard.railway.app/graphql/v2"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

print("="*90)
print("🛑 STOPPING ALL RUNNING RAILWAY BOTS")
print("="*90)

# Check projects
q_me = """
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

r_me = requests.post(API_URL, json={"query": q_me}, headers=headers).json()
print("Account:", r_me.get("data", {}).get("me", {}).get("email"))

projects = r_me.get("data", {}).get("me", {}).get("projects", {}).get("edges", [])
for p in projects:
    p_node = p["node"]
    pid = p_node["id"]
    p_name = p_node["name"]
    print(f"\nProject: {p_name} ({pid})")
    
    services = p_node.get("services", {}).get("edges", [])
    for s in services:
        s_node = s["node"]
        sid = s_node["id"]
        s_name = s_node["name"]
        print(f"  • Service: {s_name} ({sid})")
        
        # Query active deployments
        q_dep = f"""
        query {{
          deployments(input: {{ projectId: "{pid}", serviceId: "{sid}" }}) {{
            edges {{
              node {{
                id
                status
                createdAt
              }}
            }}
          }}
        }}
        """
        r_dep = requests.post(API_URL, json={"query": q_dep}, headers=headers).json()
        deps = r_dep.get("data", {}).get("deployments", {}).get("edges", [])
        
        for d in deps:
            d_node = d["node"]
            did = d_node["id"]
            d_stat = d_node["status"]
            if d_stat in ("SUCCESS", "BUILDING", "DEPLOYING", "INITIALIZING", "CRASHED", "RESTARTING"):
                print(f"    -> Cancelling active deployment {did} ({d_stat})...")
                q_cancel = f"""
                mutation {{
                  deploymentRemove(id: "{did}")
                }}
                """
                r_c = requests.post(API_URL, json={"query": q_cancel}, headers=headers).json()
                print(f"    Result: {r_c}")

print("\n" + "="*90)
print("✅ ALL RUNNING RAILWAY BOTS HAVE BEEN STOPPED")
print("="*90)
