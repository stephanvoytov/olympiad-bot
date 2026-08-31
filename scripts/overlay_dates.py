"""Overlay scraped dates onto generated olympiads.json using index mapping."""
import json

# Load generated data
with open("data/olympiads.json", encoding="utf-8") as f:
    olympiads = json.load(f)

# Load scraped data
with open("data/scraped_dates_2026.json", encoding="utf-8") as f:
    scraped = json.load(f)

# Build mapping: scraped data is in same order as article page = same order as REAL_DATA indices
# scraped[0] = index 1 (first olympiad), scraped[1] = index 2, etc.
scraped_by_index = {}
for i, r in enumerate(scraped):
    scraped_by_index[i + 1] = r  # 1-based index

updated = 0
for i, oly in enumerate(olympiads):
    idx = i + 1  # 1-based index matches REAL_DATA keys
    if idx in scraped_by_index:
        data = scraped_by_index[idx]
        if data.get("stages"):
            stages = []
            for s in data["stages"]:
                stage = {
                    "name": s["name"],
                    "date_start": s.get("date_start"),
                    "date_end": s.get("date_end"),
                }
                stages.append(stage)
            oly["stages"] = stages
            updated += 1
            print(f"  [{idx}] {oly['name'][:50]}: {len(stages)} stages")

with open("data/olympiads.json", "w", encoding="utf-8") as f:
    json.dump(olympiads, f, ensure_ascii=False, indent=2)

print(f"\nUpdated {updated} olympiads with scraped dates")
