import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"

print("="*105)
print("🔍 HISTORICAL VOLUME & LIQUIDITY AUDIT ACROSS PAST 5-MINUTE POLYMARKET MARKETS")
print("="*105)

# Query closed past 5-minute Bitcoin events across past days
try:
    r = requests.get(f"{GAMMA_HOST}/events?limit=50&closed=true&tag_slug=bitcoin", timeout=8).json()
    btc_events = [e for e in r if "btc-updown-5m" in e.get("slug", "")]
    
    # If tag search is limited, query by slugs across recent days
    if len(btc_events) < 10:
        now_ts = int(time.time() // 300) * 300
        for i in range(1, 40):
            ts = now_ts - (i * 300)
            slug = f"btc-updown-5m-{ts}"
            try:
                ev = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=2).json()
                if ev and ev[0].get("markets"):
                    btc_events.append(ev[0])
            except Exception:
                pass

    print(f"Loaded {len(btc_events)} historical 5-minute Bitcoin markets from Polymarket.\n")
    print(f"{'Market Title':<45} | {'Slug':<25} | {'Total Volume (USDC)':<20} | {'Liquidity Status'}")
    print("-" * 105)
    
    total_vol = 0.0
    for e in btc_events:
        title = e.get("title", "5-Min BTC Market")
        slug = e.get("slug", "")
        vol = float(e.get("volume", 0) or 0)
        total_vol += vol
        liq_status = "Deep Liquidity (>$5k)" if vol > 5000 else "Active Liquidity"
        print(f"{title[:43]:<45} | {slug:<25} | ${vol:<19,.2f} | {liq_status}")

    print("="*105)
    if btc_events:
        avg_vol = total_vol / len(btc_events)
        print(f"📊 HISTORICAL 5-MINUTE MARKET METRICS:")
        print(f"  • Total Markets Analyzed:           {len(btc_events)}")
        print(f"  • Total Volume Across Sample:       ${total_vol:,.2f} USDC")
        print(f"  • Average Volume Per 5-Min Market:  ${avg_vol:,.2f} USDC")
    print("="*105)

except Exception as ex:
    print("Query error:", ex)
