import time, datetime, requests, json

headers = {"User-Agent": "Mozilla/5.0"}
GAMMA_HOST = "https://gamma-api.polymarket.com"

def get_active_5m_btc_market():
    now = int(time.time())
    cur_w = (now // 300) * 300
    for w_s in [cur_w, cur_w + 300]:
        slug = f"btc-updown-5m-{w_s}"
        try:
            r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3, headers=headers).json()
            if r and r[0].get("markets"):
                m = r[0]["markets"][0]
                tokens = json.loads(m.get("clobTokenIds", "[]"))
                if len(tokens) >= 2 and now < (w_s + 300):
                    return {
                        "slug": slug,
                        "title": r[0].get("title", slug),
                        "window_start": w_s,
                        "window_end": w_s + 300,
                        "up_token": tokens[0],
                        "down_token": tokens[1],
                    }
        except Exception:
            pass
    return None

def fetch_best_asks(up_token, dn_token):
    r_up = requests.get(f"https://clob.polymarket.com/book?token_id={up_token}", headers=headers, timeout=2).json()
    r_dn = requests.get(f"https://clob.polymarket.com/book?token_id={dn_token}", headers=headers, timeout=2).json()
    
    asks_up = sorted(r_up.get("asks", []), key=lambda x: float(x["price"])) if r_up.get("asks") else []
    asks_dn = sorted(r_dn.get("asks", []), key=lambda x: float(x["price"])) if r_dn.get("asks") else []
    
    up_p = float(asks_up[0]["price"]) if asks_up else 1.0
    up_s = float(asks_up[0]["size"]) if asks_up else 0.0
    dn_p = float(asks_dn[0]["price"]) if asks_dn else 1.0
    dn_s = float(asks_dn[0]["size"]) if asks_dn else 0.0
    return up_p, up_s, dn_p, dn_s

mkt = get_active_5m_btc_market()
print(f"=== MONITORING LIVE 5M CANDLE: {mkt['slug'] if mkt else 'None'} ===")
print("Tracking every pool of shares and watching when it appears vs when it disappears...\n")

if mkt:
    active_pools = {} # pool_id -> {start_t, up_p, up_s, dn_p, dn_s, max_s, last_seen_t}
    pool_seq = 0
    
    for tick in range(1, 40): # Run 40 ticks (~20 seconds)
        t_now = time.time()
        t_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-4] + " UTC"
        up_p, up_s, dn_p, dn_s = fetch_best_asks(mkt["up_token"], mkt["down_token"])
        comb = round(up_p + dn_p, 3)
        
        # Check if sub-$1.00 cross exists
        is_cross = comb < 1.000 and up_p > 0 and dn_p > 0
        tag = f"🔥 CROSS ${comb:.3f}" if is_cross else f"   Spread ${comb:.3f}"
        
        print(f"[{t_str}] Tick {tick:02d} | UP: ${up_p:.2f} ({up_s:5.1f} sh) | DN: ${dn_p:.2f} ({dn_s:5.1f} sh) | {tag}")
        
        # Track persistent pools
        if is_cross:
            # Check if this matches an existing tracked cross pool
            found = False
            for pid, pdata in list(active_pools.items()):
                if pdata["up_p"] == up_p and pdata["dn_p"] == dn_p:
                    # Same price level cross still sitting on book!
                    pdata["last_seen_t"] = t_now
                    pdata["cur_up_s"] = up_s
                    pdata["cur_dn_s"] = dn_s
                    found = True
                    break
            if not found:
                pool_seq += 1
                active_pools[pool_seq] = {
                    "start_t": t_now,
                    "last_seen_t": t_now,
                    "start_str": t_str,
                    "up_p": up_p,
                    "up_s": up_s,
                    "dn_p": dn_p,
                    "dn_s": dn_s,
                    "cur_up_s": up_s,
                    "cur_dn_s": dn_s,
                    "comb": comb,
                    "closed": False
                }
                print(f"   --> 🟢 NEW CROSS POOL #{pool_seq} OPENED: UP {up_s:.1f}sh @ ${up_p:.2f} + DN {dn_s:.1f}sh @ ${dn_p:.2f} = ${comb:.3f}")
        
        # Check which active pools have disappeared (dried up)
        for pid, pdata in list(active_pools.items()):
            if not pdata["closed"] and (t_now - pdata["last_seen_t"]) >= 0.8:
                pdata["closed"] = True
                dur = round(pdata["last_seen_t"] - pdata["start_t"], 2)
                profit = round(1.00 - pdata["comb"], 3)
                print(f"   --> 🛑 POOL #{pid} DRIED UP after {dur}s! (Disappeared at {t_str} | Profit: +${profit:.3f})")
                
        time.sleep(0.4)
