import time, datetime, requests, json

headers = {"User-Agent": "Mozilla/5.0"}
GAMMA_HOST = "https://gamma-api.polymarket.com"

def get_active_5m_btc_market():
    now = int(time.time())
    cur_w = (now // 300) * 300
    candidates = [cur_w, cur_w + 300, cur_w - 300]

    for w_s in candidates:
        slug = f"btc-updown-5m-{w_s}"
        try:
            r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4, headers=headers).json()
            if r and r[0].get("markets"):
                m = r[0]["markets"][0]
                tokens = json.loads(m.get("clobTokenIds", "[]"))
                if len(tokens) >= 2:
                    return {
                        "slug": slug,
                        "title": r[0].get("title", slug),
                        "window_start": w_s,
                        "window_end": w_s + 300,
                        "up_token": tokens[0],
                        "down_token": tokens[1],
                    }
        except Exception as e:
            pass
    return None

mkt = get_active_5m_btc_market()
print("ACTIVE CANDLE:", mkt.get("slug") if mkt else "None")
if mkt:
    r_up = requests.get(f"https://clob.polymarket.com/book?token_id={mkt['up_token']}", headers=headers).json()
    r_dn = requests.get(f"https://clob.polymarket.com/book?token_id={mkt['down_token']}", headers=headers).json()
    
    asks_up = sorted(r_up.get("asks", []), key=lambda x: float(x["price"]))
    asks_dn = sorted(r_dn.get("asks", []), key=lambda x: float(x["price"]))
    
    print("\nUP Asks:")
    for a in asks_up[:5]:
        print(f"  ${float(a['price']):.2f} ({float(a['size']):.1f} sh)")
        
    print("\nDOWN Asks:")
    for a in asks_dn[:5]:
        print(f"  ${float(a['price']):.2f} ({float(a['size']):.1f} sh)")
        
    if asks_up and asks_dn:
        best_up = asks_up[0]
        best_dn = asks_dn[0]
        comb = float(best_up['price']) + float(best_dn['price'])
        print(f"\nLive Combined: ${comb:.3f}")
