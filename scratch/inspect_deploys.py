import os

deploy_dirs = [d for d in os.listdir('.') if os.path.isdir(d) and 'deploy' in d]
print(f"Deploy dirs: {deploy_dirs}")

for d in deploy_dirs:
    print("\n" + "="*80)
    print(f"DEPLOY DIRECTORY: {d}")
    print("="*80)
    for f in os.listdir(d):
        if f.endswith('.py'):
            path = os.path.join(d, f)
            print(f"--- File: {path} ---")
            with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                lines = fp.readlines()
                # print header constants (first 50 lines)
                for line in lines[:40]:
                    if any(k in line for k in ['STAKE', 'SHARES', 'PRICE', 'OFFSET', 'WINDOW', 'PROB', 'TIMING', 'SECONDS', 'DIFF', 'THRESHOLD', 'SLIPPAGE', 'ORDER', 'URL', 'BOT', 'VERSION', 'NAME', 'BUY', 'SIZE', 'LIMIT', 'MAX', 'MIN', 'STREAK', 'ROLLOVER']):
                        print("  ", line.strip())
