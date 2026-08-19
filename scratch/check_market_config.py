import requests
import json

slug = "btc-updown-5m-1787146800"
r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
m = r[0]["markets"][0]
print("cryptoMarketConfig:", json.dumps(m.get("cryptoMarketConfig"), indent=2))
print("umaResolutionStatuses:", m.get("umaResolutionStatuses"))
print("resolutionSource:", m.get("resolutionSource"))
