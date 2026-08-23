import os
import re

print("="*80)
print("SEARCHING ALL BOTS IN CODEBASE FOR SCALPING / BUY-AND-SELL LOGIC")
print("="*80)

for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.venv', '.git', '__pycache__', 'scratch']):
        continue
    for f in files:
        if f.endswith('.py') or f.endswith('.json'):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                txt = fp.read()
                
            keywords = ['scalp', 'sell_order', 'take_profit', 'bailout', 'buy_price', 'target_price', '0.97', '0.98', 'flip', 'cashout', 'profit_target']
            matches = [k for k in keywords if k in txt.lower()]
            if len(matches) >= 2 or 'scalper' in p.lower() or 'bailout' in p.lower() or 'flip' in p.lower():
                print(f"\n--- MATCH FOUND: {p} --- (Keywords: {matches})")
                lines = txt.split('\n')
                for i, line in enumerate(lines[:60]):
                    if any(k in line.lower() for k in ['scalp', 'sell', 'buy', 'target', 'profit', 'entry', 'exit', 'bailout', 'price']):
                        print(f"  L{i+1}: {line.strip()[:110]}")
