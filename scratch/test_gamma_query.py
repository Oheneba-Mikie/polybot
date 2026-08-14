import requests
import json

CLOB_HOST = "https://clob.polymarket.com"
market_hash = "0xf58d2a4759ac6de1e64960aca6ee47348412c26bb450e442240ea23945312523"

r = requests.get(f"{CLOB_HOST}/markets/{market_hash}")
print(f"Status Code: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print("Keys:", list(data.keys()))
    print("question:", data.get("question"))
    print("condition_id:", data.get("condition_id"))
    print("description:", data.get("description"))
    print("token_ids:", data.get("tokens"))
else:
    print(r.text)
