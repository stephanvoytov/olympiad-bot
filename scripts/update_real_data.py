"""Update REAL_DATA in generate_olympiads.py with scraped dates."""
import json
import re

# Load scraped data
with open("data/scraped_dates_2026.json", encoding="utf-8") as f:
    scraped = json.load(f)

# Build mapping: scraped[i] = index i+1
scraped_by_index = {}
for i, r in enumerate(scraped):
    scraped_by_index[i + 1] = r

# Read generate_olympiads.py
with open("scripts/generate_olympiads.py", encoding="utf-8") as f:
    content = f.read()

# For each scraped entry with stages, update REAL_DATA
for idx, data in scraped_by_index.items():
    if not data.get("stages"):
        continue
    
    # Find the entry block: "# {idx}. ...\n    {idx}: {...},"
    # Build replacement stages
    stage_lines = []
    for s in data["stages"]:
        start = s.get("date_start") or "2026-09-01"
        end = s.get("date_end") or start
        name = s["name"].replace('"', '\\"')
        stage_lines.append(f'            {{"name": "{name}", "date_start": "{start}", "date_end": "{end}"}},')
    
    new_stages = "\n".join(stage_lines)
    
    # Find the pattern for this entry's stages array
    # Match: "stages": [...], or "stages": [...]
    pattern = rf'(    {idx}: \{{[^}}]*?"stages": \[)\s*(?:\{{[^}}]*?\}},?\s*)*\]'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        old_block = match.group(0)
        # Replace stages array
        new_block = re.sub(
            r'"stages": \[.*?\]',
            f'"stages": [\n{new_stages}\n        ]',
            old_block,
            flags=re.DOTALL
        )
        content = content.replace(old_block, new_block)
        print(f"  Updated [{idx}] with {len(data['stages'])} stages")
    else:
        print(f"  Skipped [{idx}] - pattern not found")

with open("scripts/generate_olympiads.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Done!")
