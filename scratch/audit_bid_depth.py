import sys
import json
import requests

sys.stdout.reconfigure(encoding='utf-8')

CLOB_HOST = "https://clob.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"

print("="*100)
print("🔍 RESEARCH: AUDITING LIVE BID DEPTH (CAN YOU ALWAYS DUMP AT MARKET PRICE?)")
print("="*100)

# Fetch current active 5m markets
r = requests.get(f"{GAMMA_HOST}/events?limit=5&closed=false").json()
active_markets = []
for ev in r:
    if "btc-updown-5m" in ev.get("slug", ""):
        active_markets.append(ev)

print(f"Auditing {len(active_markets)} active 5-minute markets on Polymarket...\n")

for ev in active_markets:
    slug = ev.get("slug")
    mkt = ev["markets"][0]
    tids = json.loads(mkt.get("clobTokenIds") or "[]")
    print(f"📌 Market: {mkt.get('question')} ({slug})")
    
    for idx, tid in enumerate(tids):
        outcome_name = "UP" if idx == 0 else "DOWN"
        try:
            r_book = requests.get(f"{CLOB_HOST}/book?token_id={tid}", timeout=5).json()
            bids = r_book.get("bids", [])
            asks = r_book.get("asks", [])
            
            # Sort bids descending by price
            sorted_bids = sorted(bids, key=lambda b: float(b["price"]), reverse=True)
            sorted_asks = sorted(asks, key=lambda a: float(a["price"]))
            
            best_bid = sorted_bids[0] if sorted_bids else None
            best_ask = sorted_asks[0] if sorted_asks else None
            
            print(f"   [{outcome_name}] Best Ask: ${float(best_ask['price']):.2f} ({best_ask['size']} sh)" if best_ask else f"   [{outcome_name}] No Asks")
            print(f"   [{outcome_name}] Top 3 Buyers (Bids) on Book:")
            if sorted_bids:
                for b_i, b in enumerate(sorted_bids[:3]):
                    print(f"      #{b_i+1}: Price ${float(b['price']):.2f} | Available Liquidity: {float(b['size']):.2f} shares (${float(b['price'])*float(b['size']):.2f} USDC)")
            else:
                print(f"      ❌ NO BIDS AVAILABLE")
        except Exception as e:
            print(f"   Error fetching book for {outcome_name}: {e}")
    print("-" * 80)
