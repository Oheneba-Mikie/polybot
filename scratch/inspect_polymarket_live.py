import requests
import json
import time

now = int(time.time())
cur_w = (now // 300) * 300
candidates = [cur_w, cur_w + 300]

print(f"Current UTC Timestamp: {now} ({time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(now))})")

for w in candidates:
    slug = f"btc-updown-5m-{w}"
    try:
        r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=5).json()
        if r and r[0].get("markets"):
            m = r[0]["markets"][0]
            tokens = json.loads(m.get("clobTokenIds", "[]"))
            outcomes = json.loads(m.get("outcomes", "[]"))
            print(f"\n==========================================")
            print(f"Market: {slug} (Active: {now < w+300})")
            print(f"Title: {r[0].get('title')}")
            print(f"Outcomes: {outcomes}")
            print(f"Tokens: {tokens}")
            
            if len(tokens) >= 2:
                b_up = requests.get(f"https://clob.polymarket.com/book?token_id={tokens[0]}", timeout=5).json()
                b_dn = requests.get(f"https://clob.polymarket.com/book?token_id={tokens[1]}", timeout=5).json()
                
                print(f"\n--- UP ({outcomes[0] if len(outcomes)>0 else 'UP'}) Order Book ---")
                print("ASKS (Lowest 5):")
                for a in b_up.get("asks", [])[:5]:
                    print(f"  Price: ${float(a['price']):.3f} | Size: {float(a['size']):.1f} shares")
                print("BIDS (Highest 5):")
                for b in b_up.get("bids", [])[:5]:
                    print(f"  Price: ${float(b['price']):.3f} | Size: {float(b['size']):.1f} shares")
                
                print(f"\n--- DOWN ({outcomes[1] if len(outcomes)>1 else 'DOWN'}) Order Book ---")
                print("ASKS (Lowest 5):")
                for a in b_dn.get("asks", [])[:5]:
                    print(f"  Price: ${float(a['price']):.3f} | Size: {float(a['size']):.1f} shares")
                print("BIDS (Highest 5):")
                for b in b_dn.get("bids", [])[:5]:
                    print(f"  Price: ${float(b['price']):.3f} | Size: {float(b['size']):.1f} shares")
    except Exception as e:
        print(f"Error fetching {slug}: {e}")
