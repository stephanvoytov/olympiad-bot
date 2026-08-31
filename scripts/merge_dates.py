"""Merge scraped dates into generate_olympiads.py REAL_DATA."""
import json
import re

with open("data/scraped_dates_2026.json", encoding="utf-8") as f:
    scraped = json.load(f)

# Build lookup by olympiad ID
lookup = {r["id"]: r for r in scraped if r.get("stages")}

# Read current generate_olympiads.py
with open("scripts/generate_olympiads.py", encoding="utf-8") as f:
    content = f.read()

# For each scraped olympiad, update its REAL_DATA entry
for oid, data in lookup.items():
    stages = data["stages"]
    # Build the stages array for REAL_DATA
    stage_lines = []
    for s in stages:
        start = s.get("date_start") or "2026-09-01"
        end = s.get("date_end") or start
        name = s["name"].replace('"', '\\"')
        stage_lines.append(f'            {{"name": "{name}", "date_start": "{start}", "date_end": "{end}"}},')
    
    stages_str = "\n".join(stage_lines)
    
    # Find the entry in REAL_DATA by OID comment
    pattern = rf'(# {re.escape(str(oid))}\.\s+.*?\n    {oid}: \{{.*?"stages": \[).*?\]'
    replacement = rf'\1\n{stages_str}\n        ],'
    
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    if new_content != content:
        content = new_content
        print(f"  Updated [{oid}] with {len(stages)} stages")
    else:
        print(f"  Skipped [{oid}] - pattern not found")

with open("scripts/generate_olympiads.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Done!")
