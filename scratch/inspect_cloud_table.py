import requests

url = "https://polybot-sniper-mikie.fly.dev/api/state"
d = requests.get(url).json()
print("Market:", d.get("current_candle_slug"))
print("Total Crosses in Table:", len(d.get("cross_opportunities", [])))
for c in d.get("cross_opportunities", []):
    print(f"#{c.get('num')}\t{c.get('timestamp')}\tUP: {c.get('up_str')}\tDN: {c.get('dn_str')}\tCost: {c.get('comb')}\tLifespan: {c.get('lifespan')}\tProfit: {c.get('profit')}")
