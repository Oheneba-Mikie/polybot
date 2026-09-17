import requests
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

r = requests.get('https://gamma-api.polymarket.com/events?slug=btc-updown-5m-1789629900').json()
m = r[0]['markets'][0]

print("Title:", m.get('question'))
print("Resolution Source:", m.get('resolutionSource'))
print("Description:\n", m.get('description'))
