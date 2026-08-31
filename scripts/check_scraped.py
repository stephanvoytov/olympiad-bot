import json

with open("data/scraped_dates_2026.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total: {len(data)}")
print(f"With stages: {sum(1 for r in data if r.get('stages'))}")
print(f"Errors: {sum(1 for r in data if r.get('status') == 'error')}")
print()

for r in data:
    stages = r.get("stages", [])
    if stages:
        stage_str = "; ".join(s["name"] + ": " + s["raw"] for s in stages)
        print(f"  [{r['id']}] {r['name'][:50]}: {stage_str[:120]}")
