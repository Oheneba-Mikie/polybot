import requests
import json
import time

now = int(time.time())
current_window = (now // 300) * 300

print(f"Current UTC Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(now))}")

print("\n=== ACTIVE & UPCOMING 5-MINUTE POLYMARKET MARKETS ===")
for delta in range(-1, 4):
    ts = current_window + (delta * 300)
    time_str = time.strftime('%H:%M:%S', time.gmtime(ts))
    time_end_str = time.strftime('%H:%M:%S', time.gmtime(ts + 300))
    status = "EXPIRED" if now >= ts + 300 else ("ACTIVE NOW" if now >= ts else "UPCOMING")
    
    print(f"\n[WINDOW] {time_str} - {time_end_str} UTC [{status}]")
    for asset in ["btc", "eth"]:
        slug = f"{asset}-updown-5m-{ts}"
        try:
            r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=5).json()
            if r and len(r) > 0:
                e = r[0]
                m = e.get("markets", [{}])[0]
                tokens = json.loads(m.get("clobTokenIds", "[]")) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds", [])
                vol = float(m.get("volume", 0))
                
                # Fetch live order book prices for UP and DOWN
                up_ask, down_ask = 0.0, 0.0
                up_depth, down_depth = 0.0, 0.0
                if len(tokens) >= 2:
                    try:
                        b1 = requests.get(f"https://clob.polymarket.com/book?token_id={tokens[0]}", timeout=3).json()
                        b2 = requests.get(f"https://clob.polymarket.com/book?token_id={tokens[1]}", timeout=3).json()
                        if b1.get("asks"):
                            up_ask = float(b1["asks"][0]["price"])
                            up_depth = float(b1["asks"][0]["size"])
                        if b2.get("asks"):
                            down_ask = float(b2["asks"][0]["price"])
                            down_depth = float(b2["asks"][0]["size"])
                    except:
                        pass
                
                print(f"  * {e.get('title')} (Volume: ${vol:,.2f})")
                print(f"    Slug: {slug}")
                if status == "ACTIVE NOW":
                    print(f"    Live Order Book -> UP Best Ask: ${up_ask:.3f} ({up_depth:.0f} sh) | DOWN Best Ask: ${down_ask:.3f} ({down_depth:.0f} sh)")
                    print(f"    Combined Instant Cost: ${up_ask + down_ask:.3f} {'[ARBITRAGE PROFITABLE <= $0.960]' if (up_ask + down_ask <= 0.960 and up_ask > 0 and down_ask > 0) else ''}")
        except Exception as err:
            pass
