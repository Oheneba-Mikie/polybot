import json

with open("d:/Desktop/antigravity/POLYBOT/polybot/scratch/ticks_2h.json", "r") as f:
    data = json.load(f)

def dedupe_and_sort(ticks):
    seen = set()
    out = []
    for t in ticks:
        k = (t["time_utc"], round(t["up_px"], 2), round(t["dn_px"], 2), round(t["comb"], 3), t["slug"])
        if k not in seen:
            out.append(t)
            seen.add(k)
    out.sort(key=lambda x: (x["slug"], x["sec"]))
    return out

eth_all = dedupe_and_sort(data.get("eth", []))
sol_all = dedupe_and_sort(data.get("sol", []))

print(f"Total Unique ETH Crosses (<$1.00): {len(eth_all)}")
print(f"Total Unique SOL Crosses (<$1.00): {len(sol_all)}")

def make_md_table(ticks, limit=40):
    lines = []
    lines.append("| # | Elapsed (Countdown) | Time (UTC) | UP Shares on Book (Bought) & Price | DOWN Shares on Book (Bought) & Price | Total Cost | Execution Gap | How Soon It Dried Up | Guaranteed Profit |")
    lines.append("| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for idx, d in enumerate(ticks[:limit], 1):
        el_str = f"T+{d['sec']:03d}s (T-{d['countdown']:03d}s)"
        up_s = f"{d['up_sz']:.1f} sh (Bt {d['up_fill']:.1f}) @ ${d['up_px']:.2f}"
        dn_s = f"{d['dn_sz']:.1f} sh (Bt {d['dn_fill']:.1f}) @ ${d['dn_px']:.2f}"
        cents = int(round(d['comb'] * 100))
        cost_s = f"${d['comb']:.3f} ({cents:02d}¢)"
        gap_s = f"{d['gap_ms']}ms (Instant)" if d['gap_ms'] < 1000 else f"{round(d['gap_ms']/1000,1)}s (Instant)"
        prof_s = f"+${d['profit_usd']:.3f} (+{d['profit_pct']:.1f}%)"
        lines.append(f"| {idx:02d} | {el_str} | {d['time_utc']} | {up_s} | {dn_s} | {cost_s} | {gap_s} | {d['dry_up']} | {prof_s} |")
    return "\n".join(lines)

print("=== ETH TABLE SAMPLE ===")
print(make_md_table(eth_all, 15))

print("\n=== SOL TABLE SAMPLE ===")
print(make_md_table(sol_all, 15))
