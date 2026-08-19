import requests
import json
import time

def simulate_guaranteed_pair_arb():
    print("=== TESTING LATE-ROUND GUARANTEED PAIR ARBITRAGE ENGINE ===")
    print("Querying active 5-minute Polymarket BTC market order books...\n")
    
    # Fetch active markets from Gamma API
    r = requests.get("https://gamma-api.polymarket.com/events?limit=50&active=true&closed=false").json()
    btc_markets = []
    
    for event in r:
        slug = event.get("slug", "")
        if "btc-updown-5m" in slug or "btc" in slug.lower():
            for m in event.get("markets", []):
                clob_tokens = json.loads(m.get("clobTokenIds", "[]"))
                if len(clob_tokens) >= 2:
                    btc_markets.append({
                        "slug": m.get("slug"),
                        "up_id": clob_tokens[0],
                        "down_id": clob_tokens[1]
                    })
                    
    print(f"Found {len(btc_markets)} active BTC markets.")
    
    for mkt in btc_markets[:3]:
        slug = mkt["slug"]
        up_id = mkt["up_id"]
        down_id = mkt["down_id"]
        
        r_up = requests.get(f"https://clob.polymarket.com/book?token_id={up_id}").json()
        r_dn = requests.get(f"https://clob.polymarket.com/book?token_id={down_id}").json()
        
        up_asks = r_up.get("asks", [])
        dn_asks = r_dn.get("asks", [])
        
        up_ask = float(up_asks[0]["price"]) if up_asks else 1.0
        dn_ask = float(dn_asks[0]["price"]) if dn_asks else 1.0
        
        pair_cost = up_ask + dn_ask
        print(f"\nMarket: {slug}")
        print(f"  Top Ask UP:   ${up_ask:.4f}")
        print(f"  Top Ask DOWN: ${dn_ask:.4f}")
        print(f"  COMBINED PAIR COST: ${pair_cost:.4f}")
        
        MAX_PAIR_COST = 0.98
        if pair_cost <= MAX_PAIR_COST:
            profit_per_pair = 1.00 - pair_cost
            roi = (profit_per_pair / pair_cost) * 100
            print(f"  🎉 [GUARANTEED PAIR ARB DETECTED!] Pair Cost ${pair_cost:.4f} <= ${MAX_PAIR_COST:.2f}")
            print(f"     Guaranteed Profit per Pair: +${profit_per_pair:.4f} (+{roi:.2f}% Risk-Free ROI)")
        else:
            diff_cents = (pair_cost - MAX_PAIR_COST) * 100
            print(f"  Scanning: Pair Cost (${pair_cost:.4f}) > Max Budget (${MAX_PAIR_COST:.2f}). Waiting for {diff_cents:.1f}c spread convergence...")

if __name__ == "__main__":
    simulate_guaranteed_pair_arb()
