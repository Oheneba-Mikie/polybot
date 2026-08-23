import os
import re

files_to_check = []
for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.venv', '.git', '__pycache__', 'scratch']):
        continue
    for f in files:
        if f.endswith('.py'):
            files_to_check.append(os.path.join(root, f))

print(f"Checking {len(files_to_check)} files...")

for fpath in files_to_check:
    try:
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()
            # Check for double stake, 2 orders, or streak table
            has_double = 'double' in fpath.lower() or 'two' in fpath.lower() or 'dual' in fpath.lower() or 'triple' in fpath.lower()
            if '18' in code and '36' in code or 'STREAK' in code or 'streak' in code or 'place_order' in code:
                # search for order placement
                order_calls = re.findall(r'(\.create_and_post_order|\.post_order|OrderArgs|buy_order)', code)
                if len(order_calls) >= 2 or has_double or 'streak' in code.lower():
                    print("="*60)
                    print(f"MATCH: {fpath}")
                    # Find streak logic or stake calculation
                    for line in code.split('\n'):
                        if any(w in line for w in ['streak', 'STREAK', 'shares =', 'stake =', 'STAKE =', 'BASE_SHARES', 'MAX_SHARES', 'multiplier', 'scale']):
                            if not line.strip().startswith('#'):
                                print("  ", line.strip()[:100])
    except Exception as e:
        pass
