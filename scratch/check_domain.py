import requests
import json

token = 'HzdjRAVU6q3VD8cQ7IbB8GQwQsvqD_uxeqjcy9cU4v_'
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
service_id = '92085ee6-62ab-463d-a313-cab77706a35c'
environment_id = '8a457c42-0b85-401d-8aae-556195014077'

query = """
query getServiceDomains($serviceId: String!, $environmentId: String!) {
  domains(serviceId: $serviceId, environmentId: $environmentId) {
    serviceDomains {
      domain
    }
    customDomains {
      domain
    }
  }
}
"""

res = requests.post(
    'https://backboard.railway.com/graphql/v2',
    json={'query': query, 'variables': {'serviceId': service_id, 'environmentId': environment_id}},
    headers=headers
)

print(json.dumps(res.json(), indent=2))
