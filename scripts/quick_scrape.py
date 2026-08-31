"""
Quick olympiad dates scraper using requests (not playwright).
Fetches all 79 olympiads from olimpiada.ru/article/1266 and extracts
schedule tables from each /activity/{id} page.
Updates data/olympiads.json with REAL_DATA-like structure.
"""
import json
import re
import sys
import time
from collections import Counter
from bs4 import BeautifulSoup

BASE = "https://olimpiada.ru"
ARTICLE = f"{BASE}/article/1266"

MONTH_MAP = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4,
    "мая": 5, "июн": 6, "июл": 7,
    "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}


def parse_ru_date(text, year_hint=2026):
    """Parse '6 мар' -> '2027-03-06' (march=next year in 2026/27 season)."""
    t = text.strip().lower()
    m = re.match(r"(\d{1,2})\s*([а-яё]+)", t)
    if not m:
        return None
    day = int(m.group(1))
    month_str = m.group(2)
    for key, val in MONTH_MAP.items():
        if month_str.startswith(key):
            month = val
            break
    else:
        return None
    year = year_hint + 1 if month <= 7 else year_hint
    return f"{year}-{month:02d}-{day:02d}"


def parse_date_range(t):
    """Parse '31 авг...21 сен' -> ('2026-08-31', '2026-09-21')"""
    t = t.strip().lower()
    if "..." in t:
        parts = t.split("...")
    else:
        d = parse_ru_date(t)
        return (d, d)
    if len(parts) != 2:
        return (None, None)
    return (parse_ru_date(parts[0]), parse_ru_date(parts[1]))


def extract_stages(soup):
    """Extract stage table from olympiad page soup.
    Returns list of {name, date_start, date_end} or empty list."""
    stages = []
    
    # Find tables with "Что/Когда" structure
    for table in soup.find_all("table"):
        table_text = table.get_text(" ", strip=True).lower()
        if "что" not in table_text or "когда" not in table_text:
            continue
        
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            what = cells[0].get_text(strip=True)
            when = cells[-1].get_text(strip=True) if len(cells) > 1 else ""
            if not what or not when:
                continue
            
            # Skip header-like rows
            if what.lower() in ("что", "когда", ""):
                continue
            
            start, end = parse_date_range(when)
            if start or end:
                stages.append({
                    "name": what,
                    "date_start": start,
                    "date_end": end,
                    "raw": when,
                })
    
    # Deduplicate by name (keep first)
    seen = set()
    uniq = []
    for s in stages:
        if s["name"] not in seen:
            seen.add(s["name"])
            uniq.append(s)
    return uniq


def get_olympiad_data(olympiad_id):
    """Fetch a single olympiad page and extract data."""
    url = f"{BASE}/activity/{olympiad_id}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Get title
        h1 = soup.find("h1")
        name = h1.get_text(strip=True) if h1 else f"Олимпиада {olympiad_id}"
        
        # Extract stages from schedule table
        stages = extract_stages(soup)
        
        # Status detection
        body = soup.get_text(" ", strip=True).lower()
        status = "unknown"
        notes = []
        
        if "олимпиада не проводится" in body or "не проводится в этом году" in body:
            status = "not_held"
        elif any(x in body for x in ["расписание олимпиады в этом году пока не известно", "расписание следующей олимпиады ожидается"]):
            status = "no_schedule"
            # Try to extract expected month
            m = re.search(r"ожидается в (\w+ \d{4})", body)
            if m:
                notes.append(f"Ожидается: {m.group(1)}")
        elif any(x in body for x in ["регистрация открыта", "регистрация продлится"]):
            status = "registration_open"
        elif any(x in body for x in ["регистрация начнется", "регистрация откроется"]):
            status = "registration_upcoming"
        
        return {
            "id": olympiad_id,
            "name": name,
            "stages": stages,
            "status": status,
            "notes": notes,
        }
    except Exception as e:
        return {
            "id": olympiad_id,
            "name": f"Олимпиада {olympiad_id}",
            "stages": [],
            "status": "error",
            "error": str(e),
        }


def main():
    import requests  # ensure available
    
    # Step 1: Get list of 79 olympiads from article page
    print("Fetching article page...")
    r = requests.get(ARTICLE, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    
    # Find all list items with links to /activity/N
    olympiads = []
    for li in soup.select("ol li a"):
        href = li.get("href", "")
        m = re.search(r"/activity/(\d+)", href)
        if m:
            olympiads.append(int(m.group(1)))
    
    print(f"Found {len(olympiads)} olympiad IDs")
    
    # Step 2: Scrape each olympiad (with delay)
    results = []
    for i, oid in enumerate(olympiads, 1):
        print(f"[{i}/{len(olympiads)}] Scraping ID {oid}...", flush=True)
        result = get_olympiad_data(oid)
        results.append(result)
        time.sleep(0.8)  # polite delay
    
    # Step 3: Summarize
    from collections import Counter
    counts = Counter(r["status"] for r in results)
    with_stages = sum(1 for r in results if r["stages"])
    
    print(f"\n=== SUMMARY ===")
    print(f"Total: {len(results)}")
    print(f"With stages: {with_stages}")
    for s, c in sorted(counts.items()):
        print(f"  {s}: {c}")
    
    print("\nWith dates:")
    for r in results:
        if r["stages"]:
            st = "; ".join(f"{s['name']}: {s['raw']}" for s in r["stages"][:2])
            print(f"  [{r['id']}] {r['name']}: {st[:100]}")
    
    # Step 4: Save to JSON file
    output = {"olympiads": results}
    with open("scraped_dates.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\nSaved to scraped_dates.json")


if __name__ == "__main__":
    main()