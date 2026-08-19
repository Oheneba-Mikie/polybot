import re
import datetime
import time
import requests

log_file = r"C:\Users\mwx1432398\.gemini\antigravity-ide\brain\577d9cf2-66c2-4faa-9f76-d22ac955e9a9\scratch\railway_3h.log"

with open(log_file, "r", encoding="utf-16le", errors="ignore") as f:
    lines = f.readlines()

flow_re = re.compile(r"\[(\d{2}:\d{2}:\d{2}\.\d+)\] \[FLOW\] UP: \$([\d\.]+) \(Sz: ([\d\.]+)\) \| (?:DN|DOWN): \$([\d\.]+) \(Sz: ([\d\.]+)\)")

p98_windows = []
in_window = False
win_start = None
win_start_sz = 0
win_side = None
last_time = None

for line in lines:
    m = flow_re.search(line)
    if m:
        t_str, up_p, up_sz, dn_p, dn_sz = m.groups()
        up_p, up_sz, dn_p, dn_sz = float(up_p), float(up_sz), float(dn_p), float(dn_sz)
        
        # Parse timestamp to ms
        t_dt = datetime.datetime.strptime(t_str, "%H:%M:%S.%f")
        
        has_98 = (up_p == 0.98 or dn_p == 0.98)
        side = "UP" if up_p == 0.98 else ("DN" if dn_p == 0.98 else None)
        sz = up_sz if side == "UP" else (dn_sz if side == "DN" else 0)
        
        if has_98 and not in_window:
            in_window = True
            win_start = t_dt
            win_start_sz = sz
            win_side = side
        elif in_window and not has_98:
            duration_ms = (t_dt - win_start).total_seconds() * 1000.0
            p98_windows.append({
                "start": win_start.strftime("%H:%M:%S.%f")[:-3],
                "end": t_dt.strftime("%H:%M:%S.%f")[:-3],
                "side": win_side,
                "duration_ms": duration_ms,
                "start_size": win_start_sz
            })
            in_window = False

print("="*80)
print("ANALYSIS: HOW MANY MILLISECONDS DOES $0.98 STAY AVAILABLE BEFORE GETTING BOUGHT?")
print("="*80)

if p98_windows:
    for i, w in enumerate(p98_windows):
        print(f"Window {i+1}: {w['side']} @ $0.98 appeared at [{w['start']}] -> lasted for {w['duration_ms']:.1f} ms ({w['duration_ms']/1000.0:.2f}s) | Initial Size: {w['start_size']:.1f} shares")
    avg_ms = sum(w["duration_ms"] for w in p98_windows) / len(p98_windows)
    min_ms = min(w["duration_ms"] for w in p98_windows)
    max_ms = max(w["duration_ms"] for w in p98_windows)
    print("\n--- SUMMARY STATS ---")
    print(f"Average $0.98 Window Lifespan: {avg_ms:.1f} milliseconds ({avg_ms/1000.0:.2f} seconds)")
    print(f"Fastest $0.98 Fill Window:    {min_ms:.1f} milliseconds ({min_ms/1000.0:.2f} seconds)")
    print(f"Longest $0.98 Fill Window:    {max_ms:.1f} milliseconds ({max_ms/1000.0:.2f} seconds)")
else:
    print("No distinct closed windows parsed.")
print("="*80)
