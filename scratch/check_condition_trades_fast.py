import requests, json, time

now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - i * 300 for i in range(12)] # last 1 hour

print("=== CHECKING ETH & SOL 5M CONDITION TRADES ===")
for asset in ["btc", "eth", "sol"]:
    total_trades_found = 0
    sub_1_crosses = []
    
    for w in windows:
        slug = f"{asset}-updown-5m-{w}"
        try:
            r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=2).json()
            if not r or not r[0].get("markets"): continue
            cid = r[0]["markets"][0]["conditionId"]
            tr = requests.get(f"https://data-api.polymarket.com/trades?market={cid}&limit=500", timeout=2).json()
            if isinstance(tr, list):
                total_trades_found += len(tr)
                # Parse trades
                for i in range(len(tr)):
                    t1 = tr[i]
                    p1 = float(t1.get("price", 0))
                    o1 = str(t1.get("outcome", "")).upper()
                    ts1 = float(t1.get("timestamp") or 0)
                    if ts1 > 1e11: ts1 /= 1000.0
                    for j in range(i+1, min(i+20, len(tr))):
                        t2 = tr[j]
                        p2 = float(t2.get("price", 0))
                        o2 = str(t2.get("outcome", "")).upper()
                        ts2 = float(t2.get("timestamp") or 0)
                        if ts2 > 1e11: ts2 /= 1000.0
                        if abs(ts1 - ts2) <= 3.0 and ((o1 in ("UP","YES") and o2 in ("DOWN","NO")) or (o1 in ("DOWN","NO") and o2 in ("UP","YES"))):
                            c = round(p1 + p2, 3)
                            if c < 1.000:
                                up_t = t1 if o1 in ("UP","YES") else t2
                                dn_t = t2 if o1 in ("UP","YES") else t1
                                sub_1_crosses.append({
                                    "slug": slug,
                                    "time": time.strftime("%H:%M:%S", time.gmtime(ts1)),
                                    "up_px": float(up_t.get("price", 0)),
                                    "up_sz": float(up_t.get("size", 0)),
                                    "dn_px": float(dn_t.get("price", 0)),
                                    "dn_sz": float(dn_t.get("size", 0)),
                                    "comb": c,
                                    "gap_ms": int(abs(ts1 - ts2)*1000),
                                    "profit": round(1.0 - c, 3)
                                })
        except Exception as e:
            continue
            
    print(f"[{asset.upper()} 5M] Total Trades in Past 1 Hour: {total_trades_found} | Sub-$1.00 Crosses: {len(sub_1_crosses)}")
    if sub_1_crosses:
        print(f"Sample {asset.upper()} Crosses:")
        for sc in sub_1_crosses[:5]:
            print(f"  • [{sc['time']}] {sc['slug']} | UP: {sc['up_sz']:.1f}sh @ ${sc['up_px']:.2f} | DN: {sc['dn_sz']:.1f}sh @ ${sc['dn_px']:.2f} | Comb: ${sc['comb']:.3f} | Profit: +${sc['profit']:.3f}")
