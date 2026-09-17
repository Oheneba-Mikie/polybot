import json, os, datetime

with open("d:/Desktop/antigravity/POLYBOT/polybot/scratch/ticks_2h.json", "r") as f:
    data = json.load(f)

eth_ticks = data.get("eth", [])
sol_ticks = data.get("sol", [])
btc_ticks = data.get("btc", [])

def dedupe(ticks):
    seen = set()
    out = []
    for t in ticks:
        k = (t["time_utc"], t["up_px"], t["dn_px"], t["comb"], t["slug"])
        if k not in seen:
            out.append(t)
            seen.add(k)
    return out

eth_deduped = dedupe(eth_ticks)
sol_deduped = dedupe(sol_ticks)
btc_deduped = dedupe(btc_ticks)

print(f"Deduped ETH Sub-$1.00 Crosses: {len(eth_deduped)}")
print(f"Deduped SOL Sub-$1.00 Crosses: {len(sol_deduped)}")
print(f"Deduped BTC Sub-$1.00 Crosses: {len(btc_deduped)}")

# Let's filter those with >= 50 shares and >= 100 shares
eth_50 = [t for t in eth_deduped if t["up_sz"] >= 50 or t["dn_sz"] >= 50 or (t["up_fill"] >= 50 and t["dn_fill"] >= 50)]
sol_50 = [t for t in sol_deduped if t["up_sz"] >= 50 or t["dn_sz"] >= 50 or (t["up_fill"] >= 50 and t["dn_fill"] >= 50)]

print(f"ETH with 50+ shares: {len(eth_50)}")
print(f"SOL with 50+ shares: {len(sol_50)}")

with open("d:/Desktop/antigravity/POLYBOT/polybot/scratch/eth_sample.json", "w") as f:
    json.dump(eth_deduped[:30], f, indent=2)

with open("d:/Desktop/antigravity/POLYBOT/polybot/scratch/sol_sample.json", "w") as f:
    json.dump(sol_deduped[:30], f, indent=2)
