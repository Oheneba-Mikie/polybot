import os
import sys
import json
import time
import requests

sys.stdout.reconfigure(encoding='utf-8')

now = time.time()
cur_start = int(now // 300) * 300
prev_start = cur_start - 300

for s in [cur_start, prev_start]:
    slug = f"btc-updown-5m-{s}"
    print("=" * 80)
    print(f"🔍 INSPECTING POLYMARKET EVENT: {slug}")
    print("=" * 80)
    try:
        r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=5).json()
        if r and len(r) > 0:
            m = r[0]["markets"][0]
            print(f"Title:       {m.get('question')}")
            print(f"Description: {m.get('description')}")
            print(f"Market ID:   {m.get('id')}")
            print(f"ConditionId: {m.get('conditionId')}")
            print(f"OutcomePrices: {m.get('outcomePrices')}")
            print(f"Event Details Keys: {list(r[0].keys())}")
            print(f"Market Details Keys: {list(m.keys())}")
            # print all fields that look like price, strike, start, initial
            for k, v in m.items():
                if any(w in k.lower() for w in ['price', 'strike', 'start', 'initial', 'value', 'target', 'open', 'ref', 'feed']):
                    print(f"  • {k}: {v}")
        else:
            print(f"No event found for slug {slug}")
    except Exception as e:
        print("Error querying Gamma API:", e)

