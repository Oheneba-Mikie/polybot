import requests
import json

GAMMA_HOST = "https://gamma-api.polymarket.com"
market_id = "0xf58d2a4759ac6de1e64960aca6ee47348412c26bb450e442240ea23945312523"

r = requests.get(f"{GAMMA_HOST}/markets/{market_id}")
print(f"Status Code: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print("Keys in response:", list(data.keys()))
    print("question:", data.get("question"))
    print("slug:", data.get("slug"))
    print("resolved:", data.get("resolved"))
    print("outcomePrices:", data.get("outcomePrices"))
    print("outcomes:", data.get("outcomes"))
    print("clobTokenIds:", data.get("clobTokenIds"))
else:
    print(r.text)
