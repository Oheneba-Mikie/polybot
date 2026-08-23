import os
import re

for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.venv', '.git', '__pycache__', 'scratch']):
        continue
    for f in files:
        if f.endswith('.py'):
            fpath = os.path.join(root, f)
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
                code = fp.read()
                if 'PROBE_MARKS' in code or 'probe' in code.lower():
                    matches = re.findall(r'(PROBE_MARKS\s*=\s*\[[^\]]+\])', code)
                    if matches:
                        print(f"File: {fpath}")
                        for m in matches:
                            print(f"   {m}")
