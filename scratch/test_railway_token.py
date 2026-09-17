import requests

TOKEN = "AVUuWViq8WgZYftM09_5WU-D0JUHOl3H0wAd5rf0zof"
API_URL = "https://backboard.railway.app/graphql/v2"
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

q = "query { me { email } }"
resp = requests.post(API_URL, json={"query": q}, headers=headers)
print("Status Code:", resp.status_code)
print("Response text:", resp.text)
