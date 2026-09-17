import json

transcript_path = r"C:\Users\mwx1432398\.gemini\antigravity-ide\brain\7f77952b-686c-401a-812f-6fb56bac5048\.system_generated\logs\transcript_full.jsonl"
with open(transcript_path, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        data = json.loads(line)
        print(f"Line {idx}: type={data.get('type')}, source={data.get('source')}, keys={list(data.keys())}")
        if data.get("type") == "USER_INPUT":
            c = data.get("content", "")
            print(f"USER_INPUT content len={len(c)}, snippet={repr(c[:100])}")
