import json

transcript_path = r"C:\Users\mwx1432398\.gemini\antigravity-ide\brain\7f77952b-686c-401a-812f-6fb56bac5048\.system_generated\logs\transcript_full.jsonl"
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        content = data.get("content", "")
        if "Atletico Madrid vs Osasuna" in content:
            # find where it starts and ends
            idx = content.find("Atletico Madrid vs Osasuna")
            # find end of user text or next tag
            end_idx = content.find("The Bet Fox brand", idx)
            if end_idx != -1:
                end_idx = content.find("\n", end_idx + 100)
            else:
                end_idx = len(content)
            extracted = content[idx:end_idx]
            # clean out diff '+' prefix if lines have it
            cleaned_lines = []
            for l in extracted.splitlines():
                if l.startswith("+"):
                    cleaned_lines.append(l[1:])
                else:
                    cleaned_lines.append(l)
            res = "\n".join(cleaned_lines)
            with open(r"d:\Desktop\antigravity\POLYBOT\polybot\scratch\arbisp.md", "w", encoding="utf-8") as out:
                out.write(res)
            print(f"Wrote {len(cleaned_lines)} lines, {len(res)} bytes to arbisp.md")
            break
