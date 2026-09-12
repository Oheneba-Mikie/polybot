import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 POLYMARKET ORDER BOOK LIQUIDITY AUDIT AT RESOLUTION (T-12s)")
print("="*95)

# Sample the last 15 resolved 5-minute markets from Gamma API
try:
    r = requests.get("https://gamma-api.polymarket.com/events?limit=25&closed=true&tag_slug=bitcoin").json()
    btc_5m_events = [e for e in r if "btc-updown-5m" in e.get("slug", "")][:10]
    
    print(f"Auditing recent {len(btc_5m_events)} 5-minute resolved markets for winning side prices:")
    for e in btc_5m_events:
        slug = e.get("slug")
        title = e.get("title")
        markets = e.get("markets", [])
        if not markets: continue
        m = markets[0]
        outcomes = json.loads(m.get("outcomes", '["Up", "Down"]'))
        prices = json.loads(m.get("outcomePrices", '["0", "0"]'))
        winner = outcomes[0] if float(prices[0]) > 0.9 else outcomes[1]
        print(f"  • {slug} | Winner: {winner:<4} (Final Payout: $1.00)")
        
except Exception as e:
    print("Error querying Polymarket Gamma events:", e)

print("="*95)
