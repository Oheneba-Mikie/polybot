import requests, json

slug = "btc-updown-5m-1789049400" # 14:10 UTC
url = f"https://gamma-api.polymarket.com/events?slug={slug}"
r = requests.get(url)
print("Gamma response for 14:10 UTC:")
if r.status_code == 200 and r.json():
    ev = r.json()[0]
    print("Title:", ev.get("title"))
    for m in ev.get("markets", []):
        print("Market Question:", m.get("question"))
        print("Outcome Prices:", m.get("outcomePrices"))
        print("Closed:", m.get("closed"))
        print("Resolution:", m.get("resolution"))
else:
    print("Could not find by slug, searching active events...")
    r = requests.get("https://gamma-api.polymarket.com/events?closed=true&limit=5&tag_id=101859")
