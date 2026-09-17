import requests, datetime, time, sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = 'https://gamma-api.polymarket.com'
DATA_HOST  = 'https://data-api.polymarket.com'

now = int(time.time())
cur_w_s = (now // 300) * 300
windows = [cur_w_s - (i * 300) for i in range(8)] # Last 8 candles (40 mins)
windows.reverse()

cross_data = []
candles_summary = []

for w_s in windows:
    slug = f"eth-updown-5m-{w_s}"
    try:
        r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r_evt or not r_evt[0].get("markets"):
            continue
        cid = r_evt[0]["markets"][0].get("conditionId")
        trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=2000", timeout=4).json()
        if not isinstance(trades, list) or len(trades) < 5:
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
        
        # Analyze min/max prices reached for UP and DOWN in this candle
        up_prices = [t["price"] for t in parsed if t["outcome"] in ("UP","YES")]
        dn_prices = [t["price"] for t in parsed if t["outcome"] in ("DOWN","NO")]
        
        min_up = min(up_prices) if up_prices else 1.0
        min_dn = min(dn_prices) if dn_prices else 1.0
        
        candles_summary.append({
            "slug": slug,
            "min_up": min_up,
            "min_dn": min_dn,
            "best_async_pair": round(min_up + min_dn, 3),
            "trades_count": len(parsed)
        })
        
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
                        
                        cross_data.append({
                            "up_size": up_t["size"],
                            "dn_size": dn_t["size"],
                            "min_size": min(up_t["size"], dn_t["size"]),
                            "max_size": max(up_t["size"], dn_t["size"]),
                            "comb": comb,
                            "up_price": up_t["price"],
                            "dn_price": dn_t["price"]
                        })
    except Exception as e:
        pass

print("==================================================")
print("1. AVERAGE NUMBER OF SHARES ON BOTH SIDES")
print("==================================================")
if cross_data:
    avg_up = sum(x["up_size"] for x in cross_data) / len(cross_data)
    avg_dn = sum(x["dn_size"] for x in cross_data) / len(cross_data)
    avg_thin = sum(x["min_size"] for x in cross_data) / len(cross_data)
    avg_deep = sum(x["max_size"] for x in cross_data) / len(cross_data)
    
    # Medians
    cross_data.sort(key=lambda x: x["min_size"])
    med_thin = cross_data[len(cross_data)//2]["min_size"]
    cross_data.sort(key=lambda x: x["max_size"])
    med_deep = cross_data[len(cross_data)//2]["max_size"]
    
    print(f"Total crosses sampled: {len(cross_data)}")
    print(f"• Average shares on UP side:     {avg_up:.1f} shares")
    print(f"• Average shares on DOWN side:   {avg_dn:.1f} shares")
    print(f"• Average on the THIN side:      {avg_thin:.1f} shares (Median: {med_thin:.1f} sh)")
    print(f"• Average on the DEEP side:      {avg_deep:.1f} shares (Median: {med_deep:.1f} sh)")
else:
    print("No crosses found in window.")

print("\n==================================================")
print("2. LEGGED / ASYNC ARBITRAGE IN SAME 5-MINUTE CANDLE")
print("   (Buy one leg at its low, buy other leg later)")
print("==================================================")
for c in candles_summary:
    async_sum = c['best_async_pair']
    profitable = "✅ PROFITABLE" if async_sum < 1.00 else "❌ > $1.00"
    print(f"{c['slug'][-10:]} | Min UP: ${c['min_up']:.2f} | Min DN: ${c['min_dn']:.2f} | Async Sum: ${async_sum:.3f} | {profitable}")
