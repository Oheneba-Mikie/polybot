import requests
import json
import datetime
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

GAMMA_HOST = 'https://gamma-api.polymarket.com'
DATA_HOST  = 'https://data-api.polymarket.com'

now = datetime.datetime.now(datetime.timezone.utc).timestamp()
cur_w_s = int(now // 300) * 300
past_windows = [cur_w_s - (i * 300) for i in range(1, 25)] # 24 candles = 2 hours

def extract_ticks_for_market(asset_prefix, w_s):
    slug = f"{asset_prefix}-updown-5m-{w_s}"
    try:
        r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r_evt or not r_evt[0].get("markets"):
            return []
        m = r_evt[0]["markets"][0]
        cid = m.get("conditionId")
        clob_tokens = json.loads(m.get("clobTokenIds", "[]")) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds", [])
        
        trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=2000", timeout=4).json()
        if not isinstance(trades, list):
            return []
            
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
                    "countdown": 300 - int(tr_ts - w_s),
                    "price": float(t.get("price", 0)),
                    "size": float(t.get("size", 0)),
                    "outcome": str(t.get("outcome", "")).upper()
                })
        parsed.sort(key=lambda x: x["ts"])
        
        opps = []
        for i, t1 in enumerate(parsed):
            for j in range(i+1, min(i+40, len(parsed))):
                t2 = parsed[j]
                dt = t2["ts"] - t1["ts"]
                if dt > 2.0: break
                
                if (t1["outcome"] in ("UP","YES") and t2["outcome"] in ("DOWN","NO")) or (t1["outcome"] in ("DOWN","NO") and t2["outcome"] in ("UP","YES")):
                    comb = round(t1["price"] + t2["price"], 3)
                    if comb <= 0.985: # sub-$1.00 cross (does not amount to 1.0)
                        up_t = t1 if t1["outcome"] in ("UP","YES") else t2
                        dn_t = t2 if t1["outcome"] in ("UP","YES") else t1
                        
                        up_vol = sum(t["size"] for t in parsed if t["outcome"] in ("UP","YES") and abs(t["price"] - up_t["price"]) <= 0.01 and abs(t["ts"] - up_t["ts"]) <= 3.0)
                        dn_vol = sum(t["size"] for t in parsed if t["outcome"] in ("DOWN","NO") and abs(t["price"] - dn_t["price"]) <= 0.01 and abs(t["ts"] - dn_t["ts"]) <= 3.0)
                        
                        subsequent = [t for t in parsed[j+1:] if t["ts"] - t1["ts"] <= 20.0]
                        dry_up = dt
                        for sub in subsequent:
                            if (sub["outcome"] == up_t["outcome"] and abs(sub["price"] - up_t["price"]) <= 0.01) or (sub["outcome"] == dn_t["outcome"] and abs(sub["price"] - dn_t["price"]) <= 0.01):
                                dry_up = max(dry_up, sub["ts"] - t1["ts"])
                                
                        t1_str = datetime.datetime.fromtimestamp(t1["ts"], datetime.timezone.utc).strftime("%H:%M:%S")
                        
                        opps.append({
                            "asset": asset_prefix.upper(),
                            "slug": slug,
                            "sec": t1["sec"],
                            "countdown": t1["countdown"],
                            "time_utc": t1_str,
                            "gap_ms": int(dt * 1000),
                            "up_px": up_t["price"],
                            "up_sz": max(up_t["size"], round(up_vol, 1)),
                            "up_fill": up_t["size"],
                            "dn_px": dn_t["price"],
                            "dn_sz": max(dn_t["size"], round(dn_vol, 1)),
                            "dn_fill": dn_t["size"],
                            "comb": comb,
                            "profit_usd": round(1.0 - comb, 3),
                            "profit_pct": round(((1.0 - comb)/comb)*100, 1),
                            "dry_up": f"Dried up in {round(dry_up, 1)}s" if dry_up >= 1.0 else f"Dried up in {int(dry_up*1000)}ms"
                        })
        return opps
    except Exception as e:
        return []

all_eth_ticks = []
all_sol_ticks = []
all_btc_ticks = []

for w in past_windows:
    all_eth_ticks.extend(extract_ticks_for_market("eth", w))
    all_sol_ticks.extend(extract_ticks_for_market("sol", w))
    all_btc_ticks.extend(extract_ticks_for_market("btc", w))

print(f"Total ETH Sub-$1.00 Ticks Found: {len(all_eth_ticks)}")
print(f"Total SOL Sub-$1.00 Ticks Found: {len(all_sol_ticks)}")
print(f"Total BTC Sub-$1.00 Ticks Found: {len(all_btc_ticks)}")

# Print sample ticks
for name, ticks in [("ETH", all_eth_ticks), ("SOL", all_sol_ticks), ("BTC", all_btc_ticks)]:
    print(f"\n--- {name} TICKS (Total: {len(ticks)}) ---")
    for t in ticks[:10]:
        print(f"  [{t['time_utc']}] {t['slug']} | UP: {t['up_sz']}sh @ ${t['up_px']} | DN: {t['dn_sz']}sh @ ${t['dn_px']} | Comb: ${t['comb']} | Gap: {t['gap_ms']}ms | Profit: +${t['profit_usd']}")
