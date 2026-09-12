import requests
import json
import time

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"

# Current 5m slug
now = time.time()
win_start = int(now // 300) * 300
slug = f"btc-updown-5m-{win_start}"
print(f"Checking current slug: {slug}")

r = requests.get(f"{GAMMA_HOST}/events", params={"slug": slug}, timeout=5)
if r.status_code == 200 and r.json():
    mkt = r.json()[0]["markets"][0]
    token_ids = json.loads(mkt.get("clobTokenIds") or "[]")
    print("Market Title:", mkt.get("question"))
    print("Outcomes:", mkt.get("outcomes"))
    print("Token IDs:", token_ids)
    
    for i, tid in enumerate(token_ids):
        r_book = requests.get(f"{CLOB_HOST}/book", params={"token_id": tid}, timeout=5)
        if r_book.status_code == 200:
            b_data = r_book.json()
            bids = b_data.get("bids", [])
            asks = b_data.get("asks", [])
            best_bid = max([float(b["price"]) for b in bids]) if bids else "None"
            best_ask = min([float(a["price"]) for a in asks]) if asks else "None"
            print(f"Token {i} ({'UP' if i==0 else 'DOWN'}): Best Bid = {best_bid}, Best Ask = {best_ask}, Total Bids = {len(bids)}, Total Asks = {len(asks)}")
            if bids:
                print("  Top 3 Bids:", [(b["price"], b["size"]) for b in bids[:3]])
            if asks:
                print("  Top 3 Asks:", [(a["price"], a["size"]) for a in asks[:3]])
