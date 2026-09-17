import time, requests, json

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"
headers = {"User-Agent": "Mozilla/5.0"}

def inspect_all_live():
    now = int(time.time())
    cur_w = (now // 300) * 300
    
    print(f"--- LIVE 5-MINUTE ORDER BOOKS INSPECTION ({time.strftime('%H:%M:%S UTC', time.gmtime(now))}) ---")
    
    for asset in ["btc", "eth", "sol"]:
        slug = f"{asset}-updown-5m-{cur_w}"
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", headers=headers, timeout=3).json()
        if not r or not r[0].get("markets"):
            print(f"[{asset.upper()}] No active market found for {slug}")
            continue
        m = r[0]["markets"][0]
        tokens = json.loads(m.get("clobTokenIds", "[]"))
        
        r_up = requests.get(f"{CLOB_HOST}/book?token_id={tokens[0]}", headers=headers, timeout=3).json()
        r_dn = requests.get(f"{CLOB_HOST}/book?token_id={tokens[1]}", headers=headers, timeout=3).json()
        
        asks_up = sorted(r_up.get("asks", []), key=lambda x: float(x["price"]))
        asks_dn = sorted(r_dn.get("asks", []), key=lambda x: float(x["price"]))
        
        up_p = float(asks_up[0]["price"]) if asks_up else 0.0
        up_s = float(asks_up[0]["size"]) if asks_up else 0.0
        dn_p = float(asks_dn[0]["price"]) if asks_dn else 0.0
        dn_s = float(asks_dn[0]["size"]) if asks_dn else 0.0
        
        total_up_depth = sum(float(a["size"]) for a in asks_up)
        total_dn_depth = sum(float(a["size"]) for a in asks_dn)
        
        comb = round(up_p + dn_p, 3)
        print(f"  • {asset.upper()} 5m ({slug}):")
        print(f"      Best UP:   ${up_p:.2f} ({up_s:.1f} sh) | Total Ask Depth: {total_up_depth:,.0f} sh")
        print(f"      Best DOWN: ${dn_p:.2f} ({dn_s:.1f} sh) | Total Ask Depth: {total_dn_depth:,.0f} sh")
        print(f"      Comb Cost: ${comb:.3f} | Top Ask Depth >= 50: {(up_s >= 50 and dn_s >= 50)} | >= 100: {(up_s >= 100 and dn_s >= 100)}")

inspect_all_live()
