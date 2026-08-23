import os
import re

print("=== CHECKING TIMING AND LATENCY TESTS IN CODEBASE ===")
for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.venv', '.git', '__pycache__']):
        continue
    for f in files:
        if 'timing' in f.lower() or 'latency' in f.lower() or 'duration' in f.lower() or 'speed' in f.lower() or 'measure' in f.lower():
            p = os.path.join(root, f)
            print(f"\n--- File: {p} ---")
            with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                txt = fp.read()
                for line in txt.split('\n')[:40]:
                    if any(w in line.lower() for w in ['ms', 'latency', 'speed', 'roundtrip', 'ping', 'time', 'post_order', 'create_and_post']):
                        print("  ", line.strip()[:100])
