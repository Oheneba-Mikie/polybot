import requests
import json
import time

now_ts = time.time()
w_start = int(now_ts // 300) * 300
slug = f"btc-updown-5m-{w_start}"

print("="*80)
print(f"FETCHING LIVE ORDER BOOK DEPTH LADDER FOR: {slug}")
print("="*80)

r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=10).json()
market = r[0]["markets"][0]
token_ids = json.loads(market["clobTokenIds"])
outcomes = json.loads(market["outcomes"])

up_id, down_id = None, None
for i, o in enumerate(outcomes):
    if str(o).lower() in ("up", "yes"):
        up_id = token_ids[i]
    else:
        down_id = token_ids[i]

# Query Polymarket CLOB Book for UP
book_up = requests.get(f"https://clob.polymarket.com/book?token_id={up_id}", timeout=10).json()
# Query Polymarket CLOB Book for DOWN
book_down = requests.get(f"https://clob.polymarket.com/book?token_id={down_id}", timeout=10).json()

print("\n--- UP TOKEN ORDER BOOK (THE HOLES ON UP) ---")
print("BIDS (Buyers waiting in holes):")
for b in sorted(book_up.get("bids", []), key=lambda x: float(x["price"]), reverse=True)[:6]:
    print(f"  Hole at ${float(b['price']):.4f} | Size: {float(b['size']):.1f} shares (${float(b['price'])*float(b['size']):.2f} USDC)")

print("ASKS (Sellers waiting to sell):")
for a in sorted(book_up.get("asks", []), key=lambda x: float(x["price"]))[:6]:
    print(f"  Offer at ${float(a['price']):.4f} | Size: {float(a['size']):.1f} shares (${float(a['price'])*float(a['size']):.2f} USDC)")

print("\n--- DOWN TOKEN ORDER BOOK (THE HOLES ON DOWN) ---")
print("BIDS (Buyers waiting in holes):")
for b in sorted(book_down.get("bids", []), key=lambda x: float(x["price"]), reverse=True)[:6]:
    print(f"  Hole at ${float(b['price']):.4f} | Size: {float(b['size']):.1f} shares (${float(b['price'])*float(b['size']):.2f} USDC)")

print("ASKS (Sellers waiting to sell):")
for a in sorted(book_down.get("asks", []), key=lambda x: float(x["price"]))[:6]:
    print(f"  Offer at ${float(a['price']):.4f} | Size: {float(a['size']):.1f} shares (${float(a['price'])*float(a['size']):.2f} USDC)")
print("="*80)
