import os
import shutil
import requests
import json

TOKEN = "AVUuWViq8WgZYftM09_5WU-D0JUHOl3H0wAd5rf0zof"
API_URL = "https://backboard.railway.app/graphql/v2"
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# 1. Copy py_clob_client_v2
src = "d:/Desktop/antigravity/POLYBOT/polybot/py_clob_client_v2"
dst = "d:/Desktop/antigravity/POLYBOT/polybot/batch_fok_deploy/py_clob_client_v2"
if os.path.exists(dst):
    shutil.rmtree(dst)
shutil.copytree(src, dst)
print("1. Local deployment folder packaged with py_clob_client_v2.")

# 2. Get Railway project
q_me = """
query {
  me {
    email
    projects {
      edges {
        node {
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
    }
  }
}
"""
r = requests.post(API_URL, json={"query": q_me}, headers=headers).json()
projects = r.get("data", {}).get("me", {}).get("projects", {}).get("edges", [])

proj = projects[0]["node"]
proj_id = proj["id"]
env_id = proj["environments"]["edges"][0]["node"]["id"]
print(f"2. Railway Target: Project '{proj['name']}' ({proj_id}) | Environment: {env_id}")

# 3. Create or find service 'batch-fok-sniper'
existing_services = proj.get("services", {}).get("edges", [])
service_id = None
for s in existing_services:
    if s["node"]["name"] == "batch-fok-sniper":
        service_id = s["node"]["id"]
        break

if not service_id:
    m_create_svc = """
    mutation CreateService($projectId: String!, $name: String!) {
      serviceCreate(input: { projectId: $projectId, name: $name }) {
        id
        name
      }
    }
    """
    r_svc = requests.post(API_URL, json={
        "query": m_create_svc,
        "variables": {"projectId": proj_id, "name": "batch-fok-sniper"}
    }, headers=headers).json()
    service_id = r_svc["data"]["serviceCreate"]["id"]
    print(f"3. Created new Railway service: batch-fok-sniper ({service_id})")
else:
    print(f"3. Using existing Railway service: batch-fok-sniper ({service_id})")

# 4. Set environment variables on Railway
env_vars = {
    "POLYMARKET_LIVE_TRADING": "True",
    "POLYMARKET_ADDRESS": "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a",
    "POLYMARKET_API_KEY": "43f60963-1561-bd62-579b-a0573aa7aaa2",
    "POLYMARKET_API_SECRET": "1CvrOLIcfDIID4Nm2wmGzIh_m_dJgiWfJsFE7HvEKSk=",
    "POLYMARKET_API_PASSPHRASE": "a6970deebfd5851c3991c4e1e1336654a485cd658354bb341bbb67ba05db56b5",
    "POLYMARKET_PRIVATE_KEY": "0x9eff1c11ba151e32d0e632b72c6d3ca6f77593493da50e56dc820a95515a3fc7",
}

m_set_vars = """
mutation UpsertVars($projectId: String!, $environmentId: String!, $serviceId: String!, $variables: [VariableUpsertInput!]!) {
  variableUpsert(input: {
    projectId: $projectId
    environmentId: $environmentId
    serviceId: $serviceId
    variables: $variables
  })
}
"""

vars_payload = [{"name": k, "value": v} for k, v in env_vars.items()]

r_vars = requests.post(API_URL, json={
    "query": m_set_vars,
    "variables": {
        "projectId": proj_id,
        "environmentId": env_id,
        "serviceId": service_id,
        "variables": vars_payload
    }
}, headers=headers).json()
print("4. Successfully synchronized Polymarket API credentials to Railway.")

print(f"\n🚀 Ready for deployment! Service ID: {service_id}")
