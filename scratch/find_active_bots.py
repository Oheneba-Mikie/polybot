import os
import glob
import re

print("--- Inspecting service_ids.json ---")
try:
    with open('service_ids.json', 'r', encoding='utf-16') as f:
        print(f.read())
except Exception as e:
    try:
        with open('service_ids.json', 'r', encoding='utf-8') as f:
            print(f.read())
    except Exception as e2:
        print(f"Error reading service_ids.json: {e2}")

print("\n--- Inspecting deploy directories and configs ---")
for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.venv', '.git', '__pycache__']):
        continue
    for file in files:
        if file.endswith('.py'):
            full_path = os.path.join(root, file)
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if 'streak' in content.lower() or 'scale' in content.lower() or 'rollover' in content.lower() or 'shares' in content.lower():
                        # check for base stakes or streak increments
                        matches = re.findall(r'(STAKE|SHARES|BASE_STAKE|MAX_STAKE|STREAK|WIN_STREAK|MAX_SHARES).*', content, re.IGNORECASE)
                        if matches:
                            print(f"\nFile: {full_path}")
                            for m in matches[:6]:
                                print(f"  {m.strip()}")
            except Exception as e:
                pass
