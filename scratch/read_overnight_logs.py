import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('scratch/overnight_logs.txt', 'r', encoding='utf-16', errors='ignore') as fp:
    lines = fp.readlines()

print(f"Total lines in overnight_logs.txt: {len(lines)}")
print("--- FIRST 50 LINES ---")
for l in lines[:50]:
    print(l.rstrip())

print("\n--- LAST 50 LINES ---")
for l in lines[-50:]:
    print(l.rstrip())
