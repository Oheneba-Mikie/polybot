import requests, datetime, time, sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = 'https://gamma-api.polymarket.com'
DATA_HOST  = 'https://data-api.polymarket.com'

now = int(time.time())
cur_w_s = (now // 300) * 300
windows = [cur_w_s - (i * 300) for i in range(5)]
windows.reverse()

true_lifespans = []

for w_s in windows:
    slug = f"eth-updown-5m-{w_s}"
    try:
        r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r_evt or not r_evt[0].get("markets"):
            continue
        cid = r_evt[0]["markets"][0].get("conditionId")
        trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=2000", timeout=4).json()
        if not isinstance(trades, list):
            continue
            
        parsed = []
        for t in trades:
            tr_ts = t.get("timestamp") or t.get("matchTime")
            if isinstance(tr_ts, str):
                try: tr_ts = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00")).timestamp() if "T" in tr_ts else float(tr_ts)
                except: tr_ts = 0
            if tr_ts and tr_ts > 1e11: tr_ts /= 1000.0
            if w_s <= tr_ts <= w_s + 300:
                parsed.append({
                    "ts": tr_ts,
                    "sec": int(tr_ts - w_s),
                    "price": float(t.get("price", 0)),
                    "size": float(t.get("size", 0)),
                    "outcome": str(t.get("outcome", "")).upper()
                })
        parsed.sort(key=lambda x: x["ts"])
        
        for i, t1 in enumerate(parsed):
            for j in range(i+1, min(i+40, len(parsed))):
                t2 = parsed[j]
                dt = t2["ts"] - t1["ts"]
                if dt > 1.5: break
                
                if (t1["outcome"] in ("UP","YES") and t2["outcome"] in ("DOWN","NO")) or (t1["outcome"] in ("DOWN","NO") and t2["outcome"] in ("UP","YES")):
                    comb = round(t1["price"] + t2["price"], 3)
                    if comb <= 0.995:
                        up_t = t1 if t1["outcome"] in ("UP","YES") else t2
                        dn_t = t2 if t1["outcome"] in ("UP","YES") else t1
                        
                        # Find when UP died (last trade of UP at this price)
                        up_trades = [t for t in parsed if t["ts"] >= up_t["ts"] and t["outcome"] in ("UP","YES") and abs(t["price"] - up_t["price"]) <= 0.01 and t["ts"] - up_t["ts"] <= 20.0]
                        up_lifespan = max((t["ts"] - up_t["ts"]) for t in up_trades) if up_trades else 0.0
                        
                        # Find when DOWN died (last trade of DOWN at this price)
                        dn_trades = [t for t in parsed if t["ts"] >= dn_t["ts"] and t["outcome"] in ("DOWN","NO") and abs(t["price"] - dn_t["price"]) <= 0.01 and t["ts"] - dn_t["ts"] <= 20.0]
                        dn_lifespan = max((t["ts"] - dn_t["ts"]) for t in dn_trades) if dn_trades else 0.0
                        
                        # TRUE CROSS LIFESPAN is MINIMUM of the two legs!
                        # The cross dies the moment EITHER leg is exhausted!
                        true_lifespan = min(up_lifespan, dn_lifespan)
                        
                        t_str = datetime.datetime.fromtimestamp(t1["ts"], datetime.timezone.utc).strftime("%H:%M:%S")
                        true_lifespans.append({
                            "time": t_str,
                            "comb": comb,
                            "up_p": up_t["price"],
                            "dn_p": dn_t["price"],
                            "up_life": round(up_lifespan, 2),
                            "dn_life": round(dn_lifespan, 2),
                            "true_cross_life": round(true_lifespan, 2)
                        })
    except Exception as e:
        print(f"Err: {e}")

# Summary statistics
if true_lifespans:
    # Dedup by time and prices
    unique = {}
    for o in true_lifespans:
        k = f"{o['time']}_{o['comb']}"
        if k not in unique:
            unique[k] = o
    items = list(unique.values())
    
    under_500ms = sum(1 for x in items if x["true_cross_life"] < 0.5)
    from_500ms_to_1s = sum(1 for x in items if 0.5 <= x["true_cross_life"] < 1.0)
    from_1s_to_2s = sum(1 for x in items if 1.0 <= x["true_cross_life"] < 2.0)
    over_2s = sum(1 for x in items if x["true_cross_life"] >= 2.0)
    
    print(f"Total Unique Crosses Analyzed: {len(items)}\n")
    print(f"⚡ Disappeared in < 0.5s:  {under_500ms:3d} ({under_500ms/len(items)*100:.1f}%)")
    print(f"⏱️ Lasted 0.5s to 1.0s:    {from_500ms_to_1s:3d} ({from_500ms_to_1s/len(items)*100:.1f}%)")
    print(f"🎯 Lasted 1.0s to 2.0s:    {from_1s_to_2s:3d} ({from_1s_to_2s/len(items)*100:.1f}%)")
    print(f"🏆 Lasted >= 2.0s:        {over_2s:3d} ({over_2s/len(items)*100:.1f}%)\n")
    
    print("=== SAMPLE OF RECENT TRUE CROSS LIFESPANS ===")
    for x in items[-15:]:
        print(f"Time {x['time']} UTC | Comb ${x['comb']:.3f} | UP Lifespan: {x['up_life']}s | DN Lifespan: {x['dn_life']}s | TRUE Cross Lifespan: {x['true_cross_life']}s")
else:
    print("No crosses found in window.")
