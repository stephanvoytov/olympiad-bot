"""Overlay scraped dates onto generated olympiads.json - copy stages to each profile's typical_stages."""
import json

# Load generated data
with open("data/olympiads.json", encoding="utf-8") as f:
    olympiads = json.load(f)

# Load scraped dates
with open("data/scraped_dates_2026.json", encoding="utf-8") as f:
    scraped = json.load(f)

# Build mapping: scraped[i] = index i+1 (1-based)
scraped_by_index = {}
for i, r in enumerate(scraped):
    scraped_by_index[i + 1] = r

updated = 0
for i, oly in enumerate(olympiads):
    idx = i + 1
    if idx in scraped_by_index:
        data = scraped_by_index[idx]
        if data.get("stages"):
            # Copy stages to each profile's typical_stages
            for profile in oly.get("profiles", []):
                profile["typical_stages"] = data["stages"]
            oly["stages"] = data["stages"]
            updated += 1
            print(f"  [{idx}] {oly['name'][:50]}: {len(data['stages'])} stages -> {len(oly['profiles'])} profiles")

with open("data/olympiads.json", "w", encoding="utf-8") as f:
    json.dump(olympiads, f, ensure_ascii=False, indent=2)

print(f"\nUpdated {updated} olympiads, stages copied to profiles")
