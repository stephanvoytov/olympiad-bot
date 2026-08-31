"""
Scrape 2026/27 olympiad dates from olimpiada.ru.
Two formats:
  A) Table with "Что/Когда" columns
  B) Timeline with .tl_event elements (.tl_cont_s/.tl_cont_f)
Usage: python scripts/scrape_olympiad_dates.py
"""
import json
import re
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE_URL = "https://olimpiada.ru"
ARTICLE_URL = f"{BASE_URL}/article/1266"
OUTPUT_PATH = Path("data/scraped_dates_2026.json")

MONTH_MAP = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4,
    "мая": 5, "май": 5, "июн": 6, "июл": 7,
    "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}

TL_EVENT_NAMES = {
    "ereg": "Регистрация",
    "eexam": "Заключительный этап",
    "eotbor": "Отборочный этап",
    "eolimf": "Олимпиадный фестиваль",
    "efin": "Финал",
}


def log(msg: str):
    print(msg, flush=True)


def parse_ru_date(text: str, year_hint: int = 2026) -> str | None:
    text = text.strip().lower()
    m = re.match(r"(\d{1,2})?\s*([а-яё]+)", text)
    if not m:
        return None
    day = int(m.group(1)) if m.group(1) else 1
    month_str = m.group(2)
    for key, val in MONTH_MAP.items():
        if month_str.startswith(key):
            month = val
            break
    else:
        return None
    year = year_hint + 1 if month <= 7 else year_hint
    return f"{year}-{month:02d}-{day:02d}"


def parse_date_range(text: str) -> tuple[str | None, str | None]:
    text = text.strip().lower()
    text = re.sub(r"\s+(регистрация|экзамен|отборочный|заключительный|олимпиад).*", "", text)
    if "..." in text:
        parts = text.split("...")
    elif " – " in text:
        parts = text.split(" – ")
    else:
        d = parse_ru_date(text)
        return (d, d)
    if len(parts) != 2:
        return (None, None)
    return (parse_ru_date(parts[0]), parse_ru_date(parts[1]))


async def scrape_article_list(browser) -> list[dict]:
    page = await browser.new_page()
    try:
        log("  Loading article page...")
        await page.goto(ARTICLE_URL, wait_until="load", timeout=60000)
        await page.wait_for_timeout(3000)
        items = await page.locator("ol li").all()
        log(f"  Found {len(items)} list items")
        olympiads = []
        for item in items:
            try:
                link = item.locator("a").first
                href = await link.get_attribute("href")
                text = (await link.inner_text()).strip()
                m = re.search(r"/activity/(\d+)", href or "")
                if not m:
                    continue
                oid = int(m.group(1))
                name = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
                name = re.sub(r"\s*-\s*$", "", name).strip()
                url = href if href.startswith("http") else f"{BASE_URL}{href}"
                olympiads.append({"id": oid, "name": name, "url": url})
            except Exception:
                continue
        return olympiads
    finally:
        await page.close()


async def scrape_one(browser, oly: dict, sem: asyncio.Semaphore) -> dict:
    async with sem:
        page = await browser.new_page()
        try:
            oid = oly["id"]
            url = oly["url"]
            log(f"  [{oid}] loading...")
            await page.goto(url, wait_until="load", timeout=60000)
            await page.wait_for_timeout(1500)
            log(f"  [{oid}] parsing...")

            result = {
                "id": oid, "name": oly["name"], "url": url,
                "stages": [], "status": "unknown", "notes": [],
            }

            try:
                result["name"] = (await page.locator("h1").first.inner_text()).strip()
            except Exception:
                pass

            # === STATUS ===
            status_text = ""
            try:
                status_el = page.locator(".status").first
                status_text = (await status_el.inner_text()).strip().lower()
            except Exception:
                pass

            header_text = ""
            try:
                header_area = page.locator("h1").first.locator("..").first
                header_text = (await header_area.inner_text()).strip().lower()
            except Exception:
                pass

            combined = status_text + " " + header_text

            if any(x in combined for x in ["регистрация открыта", "регистрация продлится"]):
                result["status"] = "registration_open"
            elif any(x in combined for x in ["регистрация начнется", "регистрация откроется"]):
                result["status"] = "registration_upcoming"
            elif any(x in combined for x in ["регистрация закрыта", "регистрация завершена"]):
                result["status"] = "registration_closed"
            elif "расписание олимпиады в этом году пока не известно" in combined:
                result["status"] = "no_schedule"
                result["notes"].append("Расписание пока не известно")
            elif any(x in combined for x in ["расписание следующей олимпиады ожидается", "расписание ожидается"]):
                result["status"] = "schedule_upcoming"

            # === FORMAT A: TABLE ===
            all_tables = await page.locator("table").all()
            log(f"  [{oid}] found {len(all_tables)} tables")
            for table in all_tables:
                try:
                    th = (await table.inner_text()).lower()
                    if "что" not in th or "когда" not in th:
                        continue
                    log(f"  [{oid}] found schedule table")
                    rows = await table.locator("tbody tr").all()
                    if not rows:
                        rows = await table.locator("tr").all()
                    for row in rows:
                        cells = await row.locator("td").all()
                        if len(cells) < 2:
                            continue
                        what = (await cells[0].inner_text()).strip()
                        when = (await cells[-1].inner_text()).strip()
                        if not what or not when:
                            continue
                        what_l = what.lower()
                        if what_l in ("что", "когда", ""):
                            continue
                        log(f"  [{oid}]   table: {what} -> {when}")
                        start, end = parse_date_range(when)
                        result["stages"].append({
                            "name": re.sub(r"\s+", " ", what).strip(),
                            "date_start": start, "date_end": end, "raw": when,
                        })
                except Exception as e:
                    log(f"  [{oid}]   table error: {e}")
                    continue

            # === FORMAT B: TIMELINE ===
            if not result["stages"]:
                try:
                    tl_events = await page.locator(".tl_event").all()
                    if tl_events:
                        log(f"  [{oid}] found {len(tl_events)} tl_events")
                        seen = set()
                        for ev in tl_events:
                            try:
                                cls = await ev.get_attribute("class") or ""
                                event_type = ""
                                for c in cls.split():
                                    if c.startswith("e") and c != "tl_event" and len(c) > 1:
                                        event_type = c
                                        break
                                stage_name = TL_EVENT_NAMES.get(event_type, event_type or "Регистрация")
                                start_el = ev.locator(".tl_cont_s").first
                                start_text = (await start_el.inner_text()).strip() if await start_el.count() else ""
                                if not start_text:
                                    continue
                                key = f"{event_type}|{start_text}"
                                if key in seen:
                                    continue
                                seen.add(key)
                                log(f"  [{oid}]   tl: {stage_name} -> {start_text}")
                                start, end = parse_date_range(start_text)
                                result["stages"].append({
                                    "name": stage_name,
                                    "date_start": start, "date_end": end, "raw": start_text,
                                })
                            except Exception:
                                continue
                except Exception:
                    pass

            # === NOT HELD ===
            if result["status"] == "unknown" and not result["stages"]:
                try:
                    body_top = (await page.locator("body").inner_text())[:2000].lower()
                    if any(x in body_top for x in ["олимпиада не проводится", "не проводится в этом году"]):
                        result["status"] = "not_held"
                except Exception:
                    pass

            log(f"  [{oid}] done: {result['status']}, {len(result['stages'])} stages")
            return result

        except Exception as e:
            log(f"  [{oly['id']}] ERROR: {e}")
            return {"id": oly["id"], "name": oly["name"], "url": oly["url"],
                    "stages": [], "status": "error", "error": str(e)}
        finally:
            await page.close()


async def main():
    log("Scraping olimpiada.ru 2026/27...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            log("\n[1/2] Article page...")
            olympiads = await scrape_article_list(browser)
            log(f"  Got {len(olympiads)} olympiads\n")

            log("[2/2] Scraping each page (10 parallel)...")
            sem = asyncio.Semaphore(10)
            tasks = [scrape_one(browser, oly, sem) for oly in olympiads]
            results = await asyncio.gather(*tasks)
            log(f"\n  All {len(results)} done")
        finally:
            await browser.close()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with_stages = sum(1 for r in results if r.get("stages"))
    from collections import Counter
    counts = Counter(r.get("status") for r in results)
    log(f"\n=== DONE ===")
    log(f"Total: {len(results)}, with dates: {with_stages}")
    for s, c in sorted(counts.items()):
        log(f"  {s}: {c}")
    log("\nWith stages:")
    for r in results:
        if r.get("stages"):
            st = "; ".join(f"{s['name']}: {s['raw']}" for s in r["stages"])
            log(f"  [{r['id']}] {r['name']}: {st[:120]}")


if __name__ == "__main__":
    asyncio.run(main())
