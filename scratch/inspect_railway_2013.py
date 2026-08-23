import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("C:/Users/mwx1432398/.gemini/antigravity-ide/brain/de217324-78db-4e18-91f8-0ed10822cead/.system_generated/tasks/task-1173.log", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

print("="*90)
print("RAILWAY LOGS FROM 20:00 UTC TO 20:20 UTC:")
print("="*90)
for line in lines:
    if any(k in line for k in ["20:0", "20:1", "20:2", "request error", "ENTRY", "BOUGHT", "BAILOUT", "STOP LOSS", "SCALP"]):
        print(line.strip())
print("="*90)
