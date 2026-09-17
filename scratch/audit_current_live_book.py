import time, datetime, requests, json

headers = {"User-Agent": "Mozilla/5.0"}

def get_current_btc_5m_market():
    # Fetch active btc 5m market
    now = int(time.time())
    url = "https://gamma-api.polymarket.com/events?slug=btc-updown-5m"
    # Or query markets directly
    r = requests.get("https://gamma-api.polymarket.com/markets?limit=100&active=true&closed=false", headers=headers).json()
    btc_5m = [m for m in r if "btc-updown-5m" in m.get("slug", "")]
    if not btc_5m:
        return None
    # find active one
    btc_5m.sort(key=lambda x: x.get("endDate", ""), reverse=True)
    for m in btc_5m:
        clob_tokens = json.loads(m.get("clobTokenIds", "[]")) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds", [])
        if len(clob_tokens) >= 2:
            return {
                "slug": m.get("slug"),
                "question": m.get("question"),
                "up_token": clob_tokens[0],
                "down_token": clob_tokens[1],
                "end_date": m.get("endDate")
            }
    return None

mkt = get_current_btc_5m_market()
print("ACTIVE MARKET:", mkt)

if mkt:
    # Fetch order books
    r_up = requests.get(f"https://clob.polymarket.com/book?token_id={mkt['up_token']}", headers=headers).json()
    r_dn = requests.get(f"https://clob.polymarket.com/book?token_id={mkt['down_token']}", headers=headers).json()
    
    asks_up = sorted(r_up.get("asks", []), key=lambda x: float(x["price"]))
    asks_dn = sorted(r_dn.get("asks", []), key=lambda x: float(x["price"]))
    
    print("\n--- UP TOP 3 ASKS ---")
    for a in asks_up[:3]:
        print(f"  Price: ${float(a['price']):.2f} | Size: {float(a['size']):.1f} sh")
        
    print("\n--- DOWN TOP 3 ASKS ---")
    for a in asks_dn[:3]:
        print(f"  Price: ${float(a['price']):.2f} | Size: {float(a['size']):.1f} sh")
        
    if asks_up and asks_dn:
        best_up = asks_up[0]
        best_dn = asks_dn[0]
        comb = float(best_up['price']) + float(best_dn['price'])
        print(f"\nCURRENT BEST COMBINED: ${comb:.3f}")
