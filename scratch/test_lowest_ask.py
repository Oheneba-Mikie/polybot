import requests
import json
import time

now = int(time.time())
cur_w = (now // 300) * 300
slug = f"btc-updown-5m-{cur_w}"

r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
m = r[0]["markets"][0]
tokens = json.loads(m.get("clobTokenIds", "[]"))

b_up = requests.get(f"https://clob.polymarket.com/book?token_id={tokens[0]}").json()
b_dn = requests.get(f"https://clob.polymarket.com/book?token_id={tokens[1]}").json()

asks_up = b_up.get("asks", [])
asks_dn = b_dn.get("asks", [])

print(f"Total UP Asks: {len(asks_up)}")
for a in asks_up:
    print(f"  UP Ask: ${float(a['price']):.3f} | Size: {float(a['size']):.1f} sh")

print(f"\nTotal DOWN Asks: {len(asks_dn)}")
for a in asks_dn:
    print(f"  DOWN Ask: ${float(a['price']):.3f} | Size: {float(a['size']):.1f} sh")

# Lowest Ask Finder:
best_up = min(asks_up, key=lambda x: float(x["price"])) if asks_up else None
best_dn = min(asks_dn, key=lambda x: float(x["price"])) if asks_dn else None

print("\n--- Correct Lowest Ask ---")
print("Lowest UP Ask:", best_up)
print("Lowest DOWN Ask:", best_dn)
if best_up and best_dn:
    print(f"True Combined Ask: ${float(best_up['price']) + float(best_dn['price']):.3f}")
