import urllib.request
import json
import time

def analyze_past_3hours():
    print("=== PAST 3 HOURS (36 5-MINUTE WINDOWS) PAIR ARBITRAGE AUDIT ===")
    print("Checking rounds from 01:00 UTC to 04:00 UTC...\n")
    
    # 36 5-minute cycles over past 3 hours
    now_ts = int(time.time())
    start_ts = now_ts - (3 * 3600)
    
    # Round timestamps in 300-second steps
    base_ts = (start_ts // 300) * 300
    
    rounds = []
    for i in range(36):
        r_ts = base_ts + (i * 300)
        rounds.append(r_ts)
        
    print(f"Auditing {len(rounds)} 5-minute rounds...")
    
    # Query Polymarket Gamma API for resolved markets in past 3h
    try:
        url = "https://gamma-api.polymarket.com/events?slug=btc-updown-5m"
        # We can also fetch active/resolved 5m markets
        req = urllib.request.urlopen("https://gamma-api.polymarket.com/markets?limit=100&active=true&closed=true")
        data = json.loads(req.read().decode('utf-8'))
        
        btc_5m_markets = [m for m in data if "btc-updown-5m" in m.get("slug", "") or "BTC" in m.get("question", "")]
        print(f"Found {len(btc_5m_markets)} total BTC 5m markets in API response.")
    except Exception as e:
        print(f"API Fetch Error: {e}")

if __name__ == "__main__":
    analyze_past_3hours()
