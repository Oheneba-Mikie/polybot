import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

artifact_file = "C:/Users/mwx1432398/.gemini/antigravity-ide/brain/de217324-78db-4e18-91f8-0ed10822cead/complete_5m_untruncated_audit.md"

with open(artifact_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

print("="*145)
print("SUB-$1.00 OPPORTUNITIES WITH >= 100.0 SHARES AVAILABLE ON BOTH SIDES")
print("="*145)

matching = []
for line in lines:
    if "|" in line and "T+" in line:
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) >= 9:
            up_info = parts[3]
            dn_info = parts[4]
            try:
                up_sz = float(re.findall(r"([\d\.]+)\s*sh", up_info)[0])
                dn_sz = float(re.findall(r"([\d\.]+)\s*sh", dn_info)[0])
                if up_sz >= 100.0 and dn_sz >= 100.0:
                    matching.append({
                        "idx": parts[0],
                        "elapsed": parts[1],
                        "time_utc": parts[2],
                        "up": up_info,
                        "up_sz": up_sz,
                        "dn": dn_info,
                        "dn_sz": dn_sz,
                        "cost": parts[5],
                        "gap": parts[6],
                        "dry": parts[7],
                        "prof": parts[8],
                    })
            except Exception:
                pass

print(f"Total Found: {len(matching)} massive liquidity opportunities (>= 100 shares on both ends)\n")

header = f"{'#':<4} | {'Elapsed (Countdown)':<19} | {'Time (UTC)':<10} | {'UP Shares & Price':<28} | {'DOWN Shares & Price':<30} | {'Total Cost':<10} | {'How Soon It Dried Up':<22} | {'Guaranteed Profit'}"
print(header)
print("-" * len(header))

for m in matching:
    print(f"{m['idx']:<4} | {m['elapsed']:<19} | {m['time_utc']:<10} | {m['up']:<28} | {m['dn']:<30} | {m['cost']:<10} | {m['dry']:<22} | {m['prof']}")

print("="*145)
