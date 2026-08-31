import json
d = json.load(open('data/olympiads.json', encoding='utf-8'))
# Check first olympiad with stages
for o in d:
    if o.get('stages'):
        print(f"Olympiad: {o['name'][:50]}")
        print(f"  stages: {len(o['stages'])}")
        for p in o.get('profiles', [])[:2]:
            print(f"  profile {p['slug']}: typical_stages={len(p.get('typical_stages', []))}")
            if p.get('typical_stages'):
                print(f"    sample: {p['typical_stages'][0]}")
        break
