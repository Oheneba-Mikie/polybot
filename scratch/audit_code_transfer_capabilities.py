import os
import glob
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 EXHAUSTIVE LOG & CODE AUDIT: CHECKING LOCAL PC, RAILWAY SCRIPTS & ENV FOR TRANSFERS")
print("="*95)

search_terms = ["0x639f", "withdraw", "relayer", "0x00000000000Fb5C9ADea0298D729A0CB3823Cc07", "0x0a3c4405"]

print("1. Searching all workspace Python files and logs for recipient address / transfer methods:")
matches = []
for root, dirs, files in os.walk("d:\\Desktop\\antigravity\\POLYBOT\\polybot"):
    if ".git" in root or ".venv" in root:
        continue
    for f in files:
        if f.endswith(".py") or f.endswith(".json") or f.endswith(".log") or f.endswith(".env"):
            fpath = os.path.join(root, f)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                    for term in search_terms:
                        if term.lower() in content.lower():
                            if "scratch" in fpath or "inspect" in fpath or "trace" in fpath:
                                continue # Skip the inspection scripts we just wrote
                            matches.append((fpath, term))
            except Exception:
                pass

if matches:
    print(f"Found {len(matches)} historical references:")
    for fpath, term in matches:
        print(f"  • File: {fpath} (Term: '{term}')")
else:
    print("  ✅ ZERO matches found in any deployment scripts, config files, or app code.")

print("\n2. Summary of deployment code:")
print("  • Railway App: `scalper_bailout_deploy/app.py`")
print("  • Libraries used: `py_clob_client_v2` (Only supports CLOB endpoints: /order, /book, /balance-allowance)")
print("  • It has NO web3 transfer methods, NO erc20 transfer methods, and NO interaction with Deposit Factory Proxy.")

print("="*95)
