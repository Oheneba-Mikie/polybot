import os
import json

print("=== CHECKING ALL BOT FOLDERS & LOGS ===")
for b in ['bot_2', 'bot_3', 'bot_4', 'bot_5', 'bot_6', 'bot_7', 'scratch']:
    if os.path.exists(b):
        print(f"\n--- Folder: {b} ---")
        for root, dirs, files in os.walk(b):
            for f in files:
                p = os.path.join(root, f)
                if not p.endswith('.pyc') and 'py_clob_client' not in p:
                    sz = os.path.getsize(p)
                    print(f"  {p} ({sz} bytes)")
                    if f.endswith(('.json', '.txt', '.md', '.env', '.sh', '.bat')):
                        try:
                            with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                                content = fp.read()
                                print(f"    Content preview:\n{content[:300]}")
                        except Exception as e:
                            print(f"    Error reading: {e}")
