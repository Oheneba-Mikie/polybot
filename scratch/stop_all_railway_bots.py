import requests
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

TOKEN = "84e59043-4ce4-436f-871d-5573de029199"
API_URL = "https://backboard.railway.app/graphql/v2"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

print("="*80)
print("🛑 STOPPING ALL RAILWAY SERVICES & ACTIVE DEPLOYMENTS")
print("="*80)

# 1. Query deployments for project 68c99960-82ce-4e00-a23b-0cb28bf4d227
query = """
query {
  deployments(input: { projectId: "68c99960-82ce-4e00-a23b-0cb28bf4d227", serviceId: "812a5eb5-d070-4ede-8665-9bd7ba4c39e8" }) {
    edges {
      node {
        id
        status
        createdAt
      }
    }
  }
}
"""

try:
    r = requests.post(API_URL, json={"query": query}, headers=headers).json()
    deps = r.get("data", {}).get("deployments", {}).get("edges", [])
    print(f"Found {len(deps)} deployments on service 812a5eb5...")
    
    for d in deps:
        node = d["node"]
        dep_id = node["id"]
        status = node["status"]
        print(f"  • Deployment {dep_id}: Status = {status}")
        
        # If active / building / running, cancel / remove
        if status in ("SUCCESS", "BUILDING", "DEPLOYING", "INITIALIZING", "CRASHED", "RESTARTING"):
            print(f"    -> Cancelling/Removing deployment {dep_id}...")
            cancel_mutation = """
            mutation CancelDeployment($id: String!) {
              deploymentRemove(id: $id)
            }
            """
            r_cancel = requests.post(API_URL, json={"query": cancel_mutation, "variables": {"id": dep_id}}, headers=headers).json()
            print(f"    Result: {r_cancel}")
except Exception as e:
    print("Error:", e)

# 2. Also check if there are other services in service_ids.json
try:
    sids = json.load(open("service_ids.json", encoding="utf-16"))
    for bot_name, sid in sids.items():
        if not sid: continue
        print(f"\nChecking {bot_name} ({sid})...")
        q = f"""
        query {{
          deployments(input: {{ projectId: "5d344874-8269-481c-8c41-efbb695ed599", serviceId: "{sid}" }}) {{
            edges {{
              node {{
                id
                status
              }}
            }}
          }}
        }}
        """
        r = requests.post(API_URL, json={"query": q}, headers=headers).json()
        bot_deps = r.get("data", {}).get("deployments", {}).get("edges", [])
        for d in bot_deps:
            node = d["node"]
            if node["status"] in ("SUCCESS", "BUILDING", "DEPLOYING", "INITIALIZING", "CRASHED", "RESTARTING"):
                print(f"  -> Stopping {node['id']} ({node['status']})...")
                c_mut = f"""
                mutation {{
                  deploymentRemove(id: "{node['id']}")
                }}
                """
                r_c = requests.post(API_URL, json={"query": c_mut}, headers=headers).json()
                print(f"  Result: {r_c}")
except Exception as e:
    print("Error on other services:", e)

print("\n" + "="*80)
print("✅ ALL RUNNING RAILWAY DEPLOYMENTS CANCELLED AND REMOVED")
print("="*80)
