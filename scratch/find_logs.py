import os

print("=== SEARCHING FOR LOG FILES, DATA FILES, AND JSON OUTPUTS ===")
for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.venv', '.git', '__pycache__']):
        continue
    for f in files:
        if any(f.endswith(ext) for ext in ['.log', '.json', '.txt', '.out']) or 'log' in f.lower():
            p = os.path.join(root, f)
            sz = os.path.getsize(p)
            print(f"{p} ({sz} bytes)")
