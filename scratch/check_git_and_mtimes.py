import os
import subprocess
import datetime
import json

print("=== GIT STATUS & RECENT COMMITS ===")
try:
    res = subprocess.run(["git", "log", "-n", "10", "--stat"], capture_output=True, text=True)
    print(res.stdout)
except Exception as e:
    print(e)

print("\n=== FILE MODIFICATION TIMES IN REPO ===")
files_with_mtime = []
for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.venv', '.git', '__pycache__', 'scratch']):
        continue
    for f in files:
        fpath = os.path.join(root, f)
        mtime = os.path.getmtime(fpath)
        dt = datetime.datetime.fromtimestamp(mtime)
        files_with_mtime.append((dt, fpath))

files_with_mtime.sort(reverse=True)
for dt, fpath in files_with_mtime[:35]:
    print(f"{dt.strftime('%Y-%m-%d %H:%M:%S')}  {fpath}")
