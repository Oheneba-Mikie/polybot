import os

print("=== SEARCHING FOR THE TWO BOTS (BUY & SELL / SCALPER vs CHASE / TREND CATCHER) ===")
deploy_dirs = [d for d in os.listdir('.') if os.path.isdir(d) and ('deploy' in d or 'bot_' in d)]

for d in sorted(deploy_dirs):
    for f in os.listdir(d):
        if f.endswith('.py') and not f.startswith('__') and 'py_clob_client' not in f:
            p = os.path.join(d, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                txt = fp.read()
                has_sell = 'sell' in txt.lower() or 'bailout' in txt.lower() or 'pair' in txt.lower() or 'take_profit' in txt.lower()
                has_chase = 'chase' in txt.lower() or 'trend' in txt.lower() or 'catch' in txt.lower() or 'momentum' in txt.lower() or 'close' in txt.lower()
                print("="*70)
                print(f"File: {p} (Size: {len(txt)} chars)")
                # Print docstrings and overview
                for line in txt.split('\n')[:35]:
                    if line.strip().startswith(('"""', "'''", "#", "def ", "class ", "BOT_", "STRATEGY")):
                        print("  ", line.strip()[:90])
