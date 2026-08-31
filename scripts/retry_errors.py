"""Retry olympiads that previously errored (timeouts/connection issues).
5 parallel. Updates only the errored entries in data/scraped_dates_2026.json.
"""
import json
import asyncio
from pathlib import Path
import sys
sys.path.insert(0, "scripts")
from scrape_olympiad_dates import (
    scrape_one, scrape_article_list, BASE_URL, OUTPUT_PATH
)
from playwright.async_api import async_playwright


async def main():
    # Load existing results
    with open(OUTPUT_PATH, encoding="utf-8") as f:
        results = json.load(f)

    # Find errored entries
    errored = [r for r in results if r.get("status") == "error"]
    print(f"Found {len(errored)} errored olympiads to retry")

    # Need to reconstruct olympiad dicts with URLs
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            # Get the article list to map IDs to URLs
            print("Loading article list for URL mapping...")
            olympiads = await scrape_article_list(browser)
            url_by_id = {o["id"]: o for o in olympiads}

            # Build oly dicts for errored
            errored_olys = []
            for r in errored:
                oid = r["id"]
                if oid in url_by_id:
                    errored_olys.append(url_by_id[oid])
                else:
                    print(f"  [{oid}] not in article list, skipping")

            print(f"Will retry {len(errored_olys)} olympiads (5 parallel)")

            sem = asyncio.Semaphore(5)
            tasks = [scrape_one(browser, oly, sem) for oly in errored_olys]
            new_results = await asyncio.gather(*tasks)
        finally:
            await browser.close()

    # Update results: replace errored entries with new ones
    new_by_id = {r["id"]: r for r in new_results}
    for i, r in enumerate(results):
        if r.get("status") == "error" and r["id"] in new_by_id:
            results[i] = new_by_id[r["id"]]

    # Save
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Summary
    success = sum(1 for r in new_results if r.get("stages"))
    no_data = sum(1 for r in new_results if r.get("status") in ("not_held", "no_schedule", "schedule_upcoming", "registration_upcoming", "unknown") and not r.get("stages"))
    still_error = sum(1 for r in new_results if r.get("status") == "error")
    print(f"\nRetry results:")
    print(f"  With stages: {success}")
    print(f"  No data: {no_data}")
    print(f"  Still errored: {still_error}")


if __name__ == "__main__":
    asyncio.run(main())
