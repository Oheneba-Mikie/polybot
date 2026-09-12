import subprocess
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 COMPREHENSIVE GIT HISTORY SECURITY SCAN: SEARCHING ALL COMMITS FOR LEAKED SECRETS")
print("="*95)

# Get all commit hashes
res = subprocess.run(["git", "log", "--format=%H %s"], capture_output=True, text=True, cwd="d:\\Desktop\\antigravity\\POLYBOT\\polybot")
commits = res.stdout.strip().split("\n")

print(f"Total Commits in History: {len(commits)}\n")

patterns = [
    (r"0x[a-fA-F0-9]{64}", "64-char Hex Private Key"),
    (r"POLYMARKET_PRIVATE_KEY\s*=\s*[^\n]+", "POLYMARKET_PRIVATE_KEY definition"),
    (r"POLYMARKET_API_SECRET\s*=\s*[^\n]+", "POLYMARKET_API_SECRET definition"),
    (r"CLOB_SECRET\s*=\s*[^\n]+", "CLOB_SECRET definition"),
    (r"PRIVATE_KEY\s*=\s*[^\n]+", "PRIVATE_KEY definition")
]

leaks_found = []

for c_line in commits:
    if not c_line.strip(): continue
    c_hash, c_msg = c_line.split(" ", 1)
    
    # Check diff for this commit
    diff_res = subprocess.run(["git", "show", c_hash], capture_output=True, text=True, cwd="d:\\Desktop\\antigravity\\POLYBOT\\polybot", errors="ignore")
    diff_text = diff_res.stdout
    
    for pat, desc in patterns:
        matches = re.findall(pat, diff_text)
        if matches:
            for m in matches:
                # Mask secret
                masked = m[:12] + "..." + m[-6:] if len(m) > 18 else m
                leaks_found.append((c_hash[:8], c_msg, desc, masked))

if leaks_found:
    print(f"⚠️ FOUND {len(leaks_found)} POTENTIAL SENSITIVE STRINGS IN GIT COMMITS:")
    for h, msg, desc, m in set(leaks_found):
        print(f"  • Commit [{h}] \"{msg}\":")
        print(f"    Type:   {desc}")
        print(f"    Sample: {m}\n")
else:
    print("✅ ZERO exposed private keys or secrets found in git commit diffs.")

print("="*95)
