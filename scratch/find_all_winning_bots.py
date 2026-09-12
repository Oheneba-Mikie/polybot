import glob
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== ALL BOT STRATEGIES IN WORKSPACE ===")
for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.venv', '.git', '__pycache__', 'scratch', 'node_modules']):
        continue
    for f in sorted(files):
        if f.endswith('.py') and not f.startswith('test') and not f.startswith('auto_') and not f.startswith('check_'):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                lines = [fp.readline().strip() for _ in range(35)]
            doc = [l for l in lines if l.startswith('#') or '"""' in l or 'Bot' in l or 'Strategy' in l or 'Sprint' in l or 'Win' in l or 'Rules' in l or 'Trigger' in l]
            if doc:
                print(f"\n--- {p} ---")
                for d in doc[:8]:
                    print("  ", d)
