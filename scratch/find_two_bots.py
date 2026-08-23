import os
import glob

print("=== CHECKING ALL BOT PYTHON SCRIPTS IN ROOT & DEPLOYS ===")
bots = []
for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.venv', '.git', '__pycache__', 'scratch']):
        continue
    for f in files:
        if f.endswith('.py'):
            bots.append(os.path.join(root, f))

for b in sorted(bots):
    with open(b, 'r', encoding='utf-8', errors='ignore') as fp:
        lines = fp.readlines()
        doc = []
        for l in lines[:30]:
            if '"""' in l or "'''" in l or '#' in l or 'bot' in l.lower() or 'trend' in l.lower() or 'scalp' in l.lower() or 'chase' in l.lower() or 'sell' in l.lower():
                doc.append(l.strip())
        print(f"\n--- {b} ---")
        print("   " + "\n   ".join(doc[:10]))
