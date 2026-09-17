import json

transcript_path = r"C:\Users\mwx1432398\.gemini\antigravity-ide\brain\7f77952b-686c-401a-812f-6fb56bac5048\.system_generated\logs\transcript_full.jsonl"
with open(transcript_path, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        if idx == 5:
            data = json.loads(line)
            print("Keys:", data.keys())
            for k in data:
                val = str(data[k])
                print(f"Key {k}: len={len(val)}, preview={val[:200]}")
