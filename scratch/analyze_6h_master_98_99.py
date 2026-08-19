import re

log_file = r"C:\Users\mwx1432398\.gemini\antigravity-ide\brain\577d9cf2-66c2-4faa-9f76-d22ac955e9a9\scratch\railway_3h.log"

with open(log_file, "r", encoding="utf-16le", errors="ignore") as f:
    lines = f.readlines()

print(f"Total Lines in 6-Hour Master Dump: {len(lines)}")

flow_re = re.compile(r"\[(\d{2}:\d{2}:\d{2}\.\d+)\] \[FLOW\] UP: \$([\d\.]+) \(Sz: ([\d\.]+)\) \| (?:DN|DOWN): \$([\d\.]+) \(Sz: ([\d\.]+)\)")

p98_occurrences = []
p99_occurrences = []

for line in lines:
    m = flow_re.search(line)
    if m:
        t, up_p, up_sz, dn_p, dn_sz = m.groups()
        up_p, up_sz, dn_p, dn_sz = float(up_p), float(up_sz), float(dn_p), float(dn_sz)
        
        if up_p == 0.98 or dn_p == 0.98:
            side = "UP" if up_p == 0.98 else "DN"
            sz = up_sz if side == "UP" else dn_sz
            p98_occurrences.append((t, side, 0.98, sz, line.strip()))
        if up_p == 0.99 or dn_p == 0.99:
            side = "UP" if up_p == 0.99 else "DN"
            sz = up_sz if side == "UP" else dn_sz
            p99_occurrences.append((t, side, 0.99, sz, line.strip()))

print(f"\nTotal $0.98 appearances found: {len(p98_occurrences)}")
print(f"Total $0.99 appearances found: {len(p99_occurrences)}")

print("\n--- SAMPLE $0.98 APPEARANCES & SIZES AVAILABLE ---")
for t, side, p, sz, raw in p98_occurrences[:15]:
    print(f"[{t}] {side} @ $0.98 | Available Size: {sz:.1f} shares")

print("\n--- SAMPLE $0.99 APPEARANCES & SIZES AVAILABLE ---")
for t, side, p, sz, raw in p99_occurrences[:15]:
    print(f"[{t}] {side} @ $0.99 | Available Size: {sz:.1f} shares")
