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

# Fetch all recent events with slug btc-updown
r = requests.get(f"{GAMMA_HOST}/events?limit=100&closed=true").json()

btc_events = []
for ev in r:
    slug = ev.get("slug", "")
    if "btc-updown-5m" in slug:
        for m in ev.get("markets", []):
            clob_tokens = json.loads(m.get("clobTokenIds", "[]"))
            outcomes = json.loads(m.get("outcomes", "[]"))
            if len(clob_tokens) >= 2:
                up_id = clob_tokens[0]
                dn_id = clob_tokens[1]
                if len(outcomes) >= 2 and outcomes[0].lower() not in ("up", "yes"):
                    up_id, dn_id = clob_tokens[1], clob_tokens[0]
                btc_events.append({
                    "slug": slug,
                    "title": m.get("question", slug),
                    "condition_id": m.get("conditionId"),
                    "up_id": up_id,
                    "down_id": dn_id,
                })

print(f"Found {len(btc_events)} closed 5m BTC events.")

# Also let's inspect the 12 events we captured live earlier to get the exact pair combinations!
with open("scratch/live_5m_pair_arb_audit.json") as f:
    live_audit = json.load(f)

print("\n=== COMBINATIONS DETECTED IN LIVE STREAM (DETAILED BREAKDOWN) ===")
combo_stats = defaultdict(lambda: {"count": 0, "shares": 0.0, "profit": 0.0, "samples": []})

for op in live_audit.get("opportunities", []):
    up_p = op["initial_up_ask"]
    dn_p = op["initial_down_ask"]
    cost = op["min_pair_cost"]
    sh = op["max_available_shares"]
    pft = op["max_profit_usd"]
    
    # Categorize by pair structure
    pair_label = f"UP @ ${up_p:.2f} + DOWN @ ${dn_p:.2f}  --> Total: ${cost:.2f}"
    combo_stats[pair_label]["count"] += 1
    combo_stats[pair_label]["shares"] += sh
    combo_stats[pair_label]["profit"] += pft
    combo_stats[pair_label]["samples"].append(f"{op['start_dt']} (Dur: {op['duration_ms']:.1f}ms, Shares: {sh:.1f})")

print(f"{'PAIR COMBINATION (PRICES)':<45} | {'COUNT':<6} | {'TOTAL SHARES':<14} | {'PROFIT POTENTIAL'}")
print("="*95)
for label, data in sorted(combo_stats.items(), key=lambda x: x[1]["shares"], reverse=True):
    print(f"{label:<45} | {data['count']:<6} | {data['shares']:<14.1f} | +${data['profit']:.4f}")
    for s in data["samples"][:2]:
        print(f"    ↳ {s}")
