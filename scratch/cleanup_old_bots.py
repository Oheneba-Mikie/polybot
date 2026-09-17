import requests
import json

token = 'HzdjRAVU6q3VD8cQ7IbB8GQwQsvqD_uxeqjcy9cU4v_'
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# List of old services in alluring-intuition
old_services = [
    '548403c0-4dbd-404a-b6a3-5089ac64f371',
    '4e12db8f-768c-4c4d-aeb6-47e4d347d860',
    'f835fc4b-08ad-4cd6-b2b8-06a789ad1d11',
    'a36a7cf8-c43d-42af-a08f-35463542bfd7',
    'fff75831-b361-4bb8-aa7e-b619af73bec5',
    'cf5e9773-e4da-4a3c-abb6-e6c4a6337670',
    'ee77e130-eafd-49a9-ab82-ca9d7d1609ee',
    '9008bf5b-2ab2-41a1-9581-b2bda3c74bb7'
]

# Delete service mutation
mutation = """
mutation deleteService($id: String!) {
  serviceDelete(id: $id)
}
"""

for sid in old_services:
    res = requests.post(
        'https://backboard.railway.com/graphql/v2',
        json={'query': mutation, 'variables': {'id': sid}},
        headers=headers
    )
    print(f"Delete service {sid}:", res.json())

# Also delete old scalper service in polybot-97-scalper if inactive
res = requests.post(
    'https://backboard.railway.com/graphql/v2',
    json={'query': mutation, 'variables': {'id': '812a5eb5-d070-4ede-8665-9bd7ba4c39e8'}},
    headers=headers
)
print("Delete old scalper service 812a5eb5-d070-4ede-8665-9bd7ba4c39e8:", res.json())

# Also delete old project alluring-intuition
del_proj_mutation = """
mutation deleteProject($id: String!) {
  projectDelete(id: $id)
}
"""
res_proj = requests.post(
    'https://backboard.railway.com/graphql/v2',
    json={'query': del_proj_mutation, 'variables': {'id': '5d344874-8269-481c-8c41-efbb695ed599'}},
    headers=headers
)
print("Delete project alluring-intuition:", res_proj.json())
