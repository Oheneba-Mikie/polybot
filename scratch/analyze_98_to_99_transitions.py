import re

log_file = r"D:\Desktop\antigravity\POLYBOT\polybot\scratch\recent_2h_flow_logs.txt"

with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

print(f"Total Log Lines: {len(lines)}")

# Pattern: [HH:MM:SS.mmm] [FLOW] UP: $0.XXXX (Sz: YYY.Y) | DN: $0.ZZZZ (Sz: WWW.W) | ...
flow_re = re.compile(r"\[(\d{2}:\d{2}:\d{2}\.\d+)\] \[FLOW\] UP: \$([\d\.]+) \(Sz: ([\d\.]+)\) \| DN: \$([\d\.]+) \(Sz: ([\d\.]+)\)")

cycles = []
current_cycle = {"name": "initial", "flows": []}

for line in lines:
    if "--- NEW CYCLE:" in line:
        if current_cycle["flows"]:
            cycles.append(current_cycle)
        current_cycle = {"name": line.strip(), "flows": []}
    m = flow_re.search(line)
    if m:
        t, up_p, up_sz, dn_p, dn_sz = m.groups()
        current_cycle["flows"].append({
            "time": t,
            "up_p": float(up_p),
            "up_sz": float(up_sz),
            "dn_p": float(dn_p),
            "dn_sz": float(dn_sz),
            "raw": line.strip()
        })

if current_cycle["flows"]:
    cycles.append(current_cycle)

print(f"Total Cycles Found: {len(cycles)}\n")

for i, c in enumerate(cycles):
    print("="*80)
    print(f"CYCLE {i+1}: {c['name']} (Total Ticks: {len(c['flows'])})")
    print("="*80)
    
    # Check 0.98 and 0.99 appearances
    p98_count = 0
    p99_count = 0
    
    transitions_98_to_99 = []
    
    prev_high = None
    for f in c["flows"]:
        high_p = max(f["up_p"], f["dn_p"])
        high_side = "UP" if f["up_p"] > f["dn_p"] else "DN"
        high_sz = f["up_sz"] if high_side == "UP" else f["dn_sz"]
        
        if high_p == 0.98:
            p98_count += 1
        elif high_p == 0.99:
            p99_count += 1
            
        if prev_high == 0.98 and high_p == 0.99:
            transitions_98_to_99.append((f["time"], high_side, high_sz))
        prev_high = high_p
        
    print(f"  $0.98 Ticks Seen: {p98_count}")
    print(f"  $0.99 Ticks Seen: {p99_count}")
    print(f"  Direct 0.98 -> 0.99 Transition Moments: {len(transitions_98_to_99)}")
    for t_time, t_side, t_sz in transitions_98_to_99[:5]:
        print(f"    -> Jumped from $0.98 to $0.99 on {t_side} at {t_time} with available size: {t_sz:.1f} shares")
    
    # Print sample sequence of 0.98 -> 0.99
    sample_seq = [f for f in c["flows"] if max(f["up_p"], f["dn_p"]) in (0.97, 0.98, 0.99)]
    if sample_seq:
        print("\n  Sample Sequence of 0.97 -> 0.98 -> 0.99 progression:")
        for s in sample_seq[:8]:
            print(f"    [{s['time']}] UP: ${s['up_p']:.4f} (Sz: {s['up_sz']:.1f}) | DN: ${s['dn_p']:.4f} (Sz: {s['dn_sz']:.1f})")
    print()
