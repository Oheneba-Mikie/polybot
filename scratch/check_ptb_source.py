import requests
import json

slug = "btc-updown-5m-1787146800"
r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
print("EVENT DETAILS:")
if r:
    m = r[0]["markets"][0]
    print("Title:", m.get("question"))
    print("Description:", m.get("description"))
    print("Group Item Title:", m.get("groupItemTitle"))
    print("Strike Price field:", m.get("strikePrice"))
    print("Raw Market Keys:", list(m.keys()))
