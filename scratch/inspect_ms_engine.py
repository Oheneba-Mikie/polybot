import os

print("="*80)
print("EXTRACTING MILLISECOND EXECUTION ENGINE FROM PREVIOUS BOT")
print("="*80)

with open("combined_railway_deploy/app.py", "r", encoding="utf-8") as f:
    code = f.read()

lines = code.split("\n")
print(f"Total lines: {len(lines)}")

# Search for the core trading loop, WS feed, probe_book, and execution functions
sections = []
recording = False
current_section = []
sec_name = ""

for i, line in enumerate(lines):
    if any(k in line for k in ["class WSFeed", "def probe_book", "def execute_trade", "def run_guard_rail_bot", "def place_order", "create_and_post"]):
        print(f"\n--- Found Anchor at Line {i+1}: {line.strip()[:80]} ---")
        for j in range(max(0, i-2), min(len(lines), i+35)):
            print(f"  {j+1:4d}: {lines[j]}")
