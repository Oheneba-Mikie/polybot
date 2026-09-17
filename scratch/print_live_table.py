import requests

res = requests.get("http://127.0.0.1:8080/api/state").json()
print("Market:", res.get("current_candle_slug"))
print("Window Ends:", res.get("candle_ends_at_utc"))
print("Seconds Remaining:", res.get("seconds_remaining"))
print("Current Book:", f"UP ${res.get('up_best_ask')} ({res.get('up_depth')} sh) + DN ${res.get('down_best_ask')} ({res.get('down_depth')} sh) = ${res.get('combined_cost')}")
print("\n--- LIVE RECORDED CROSSES IN ACTIVE WINDOW ---")
crosses = res.get("cross_opportunities", [])
print(f"Total Crosses Recorded: {len(crosses)}")
for c in crosses:
    print(f"#{c.get('num')} | {c.get('timestamp')} | UP: {c.get('up_str')} | DN: {c.get('dn_str')} | Cost: {c.get('comb')} | Lifespan: {c.get('lifespan')} | Profit: {c.get('profit')}")
