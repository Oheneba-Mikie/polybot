import os
import sys
import json
import time
import datetime
import requests
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST = "https://data-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"

print("=== FETCHING RECENT 5-MINUTE BTC MARKETS (PAST 60 MINUTES) ===")

# 1. Fetch recent 5m BTC markets
r = requests.get(f"{GAMMA_HOST}/events?limit=50&active=false&closed=true").json()
now = time.time()
one_hour_ago = now - 3600

recent_btc_events = []
for ev in r:
    slug = ev.get("slug", "")
    if "btc-updown-5m" in slug or "btc" in slug.lower():
        start_ts = ev.get("startDate")
        # Try to parse timestamp
        mkts = ev.get("markets", [])
        if mkts:
            m = mkts[0]
            clob_tokens = json.loads(m.get("clobTokenIds", "[]"))
            outcomes = json.loads(m.get("outcomes", "[]"))
            if len(clob_tokens) >= 2:
                up_id = clob_tokens[0]
                dn_id = clob_tokens[1]
                if len(outcomes) >= 2 and outcomes[0].lower() not in ("up", "yes"):
                    up_id, dn_id = clob_tokens[1], clob_tokens[0]
                recent_btc_events.append({
                    "slug": slug,
                    "title": m.get("question", slug),
                    "condition_id": m.get("conditionId"),
                    "up_id": up_id,
                    "down_id": dn_id,
                    "end_date": m.get("endDate")
                })

# Also fetch currently active events
r_act = requests.get(f"{GAMMA_HOST}/events?limit=10&active=true&closed=false").json()
for ev in r_act:
    slug = ev.get("slug", "")
    if "btc-updown-5m" in slug or "btc" in slug.lower():
        mkts = ev.get("markets", [])
        if mkts:
            m = mkts[0]
            clob_tokens = json.loads(m.get("clobTokenIds", "[]"))
            outcomes = json.loads(m.get("outcomes", "[]"))
            if len(clob_tokens) >= 2:
                up_id = clob_tokens[0]
                dn_id = clob_tokens[1]
                if len(outcomes) >= 2 and outcomes[0].lower() not in ("up", "yes"):
                    up_id, dn_id = clob_tokens[1], clob_tokens[0]
                recent_btc_events.append({
                    "slug": slug,
                    "title": m.get("question", slug),
                    "condition_id": m.get("conditionId"),
                    "up_id": up_id,
                    "down_id": dn_id,
                    "end_date": m.get("endDate")
                })

print(f"Found {len(recent_btc_events)} recent 5m BTC markets to analyze.\n")

# Analyze trade stream for each market
pair_combinations_frequency = defaultdict(lambda: {
    "count": 0,
    "total_shares": 0.0,
    "total_usd_volume": 0.0,
    "up_price_range": [],
    "down_price_range": [],
    "min_cost": 1.0,
    "avg_cost": 0.0,
    "timestamps": []
})

sub_100_events = []

for mkt in recent_btc_events[:10]:
    cid = mkt["condition_id"]
    slug = mkt["slug"]
    
    # Query trade history for this market
    try:
        r_trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=500", timeout=10).json()
    except Exception as e:
        continue
    
    if not r_trades:
        continue
    
    # Sort trades by timestamp
    trades = sorted(r_trades, key=lambda x: x.get("timestamp", 0))
    
    # Map trades by second
    sec_buckets = defaultdict(lambda: {"up": [], "down": []})
    for t in trades:
        ts = t.get("timestamp", 0)
        outcome = str(t.get("outcome", "")).lower()
        px = float(t.get("price") or 0)
        sz = float(t.get("size") or 0)
        
        if outcome in ("up", "yes"):
            sec_buckets[ts]["up"].append((px, sz))
        elif outcome in ("down", "no"):
            sec_buckets[ts]["down"].append((px, sz))

    # Cross match up & down prices in overlapping/adjacent seconds (within 2 seconds)
    sorted_secs = sorted(sec_buckets.keys())
    last_up_px = None
    last_dn_px = None
    
    for s in sorted_secs:
        b = sec_buckets[s]
        if b["up"]:
            last_up_px = b["up"][-1][0]
        if b["down"]:
            last_dn_px = b["down"][-1][0]
            
        if last_up_px is not None and last_dn_px is not None:
            comb = round(last_up_px + last_dn_px, 4)
            dt_str = datetime.datetime.fromtimestamp(s, datetime.timezone.utc).strftime("%H:%M:%S")
            
            if comb < 1.00:
                pair_key = f"UP @ ${last_up_px:.2f} + DOWN @ ${last_dn_px:.2f} = ${comb:.2f}"
                entry = pair_combinations_frequency[pair_key]
                entry["count"] += 1
                entry["min_cost"] = min(entry["min_cost"], comb)
                entry["timestamps"].append(dt_str)
                
                sub_100_events.append({
                    "time": dt_str,
                    "market": slug,
                    "up_price": last_up_px,
                    "down_price": last_dn_px,
                    "combined_cost": comb,
                    "discount_cents": round((1.00 - comb) * 100, 2)
                })

print("="*100)
print(f"{'PAIR COMBINATION':<45} | {'OCCURRENCES':<12} | {'COMBINED COST':<15} | {'DISCOUNT (PROFIT)'}")
print("="*100)

sorted_pairs = sorted(pair_combinations_frequency.items(), key=lambda x: x[1]["count"], reverse=True)
for p_key, data in sorted_pairs[:25]:
    cost = data["min_cost"]
    disc = (1.00 - cost) * 100
    print(f"{p_key:<45} | {data['count']:<12} | ${cost:<14.2f} | +{disc:.1f}¢ per pair")

print("\n" + "="*100)
print(f"Total Sub-$1.00 Pair Events Identified Across Past Markets: {len(sub_100_events)}")
print("="*100)

with open("scratch/past_pairs_analysis.json", "w") as fp:
    json.dump({
        "total_events": len(sub_100_events),
        "frequent_pairs": sorted_pairs,
        "raw_events": sub_100_events
    }, fp, indent=2)
