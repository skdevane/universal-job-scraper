"""
Job Scraper -- AI-Powered, Chat-Controlled
==========================================
Run by the AI on your behalf. You only interact via chat.

Phases:
  1. Headed browser opens, navigates to filtered URL
  2. Detects & pauses on CAPTCHA -- user notified via chat
  3. Sweeps all job links across all pages
  4. Parallel Playwright tabs fetch JS-rendered job descriptions
  5. Saves to data/<company>_jobs_<date>.json + .csv
"""

import asyncio
import csv
import json
import argparse
import sys
import time
import re
from datetime import date
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext, Browser


# --- LOGGER (writes to both stdout and log file) ------------------------------

LOG_FILE = Path("scraper_output.log")

class TeeLogger:
    """Writes to both the real stdout and a log file simultaneously."""
    def __init__(self):
        self._stdout = sys.stdout
        self._log    = open(LOG_FILE, "w", encoding="utf-8", buffering=1)

    def write(self, msg):
        self._stdout.write(msg)
        self._log.write(msg)

    def flush(self):
        self._stdout.flush()
        self._log.flush()

    def close(self):
        self._log.close()

sys.stdout = TeeLogger()


# --- CONFIG -------------------------------------------------------------------

PARALLEL_TAB_LIMIT = 5          # Concurrent Playwright tabs for description fetch
PAGE_LOAD_WAIT_MS  = 2500       # Wait after pagination click
SCROLL_PAUSE_MS    = 800        # Pause after auto-scroll
DESC_WAIT_MS       = 3000       # Wait for JS to render job description
MAX_PAGES          = 30         # Safety cap on pagination
CAPTCHA_POLL_SEC   = 3          # Polling interval while waiting for CAPTCHA solve


# --- CAPTCHA DETECTION --------------------------------------------------------

CAPTCHA_SIGNALS = [
    "captcha", "robot", "are you human", "verify you are", "i'm not a robot",
    "cloudflare", "ddos", "access denied", "just a moment", "checking your browser",
    "unusual traffic", "please verify", "security check",
]

async def detect_captcha(page: Page) -> bool:
    try:
        title = (await page.title()).lower()
        if any(sig in title for sig in CAPTCHA_SIGNALS):
            return True
        body = await page.evaluate("() => document.body.innerText.slice(0, 3000).toLowerCase()")
        if any(sig in body for sig in CAPTCHA_SIGNALS):
            return True
        for frame in page.frames:
            if any(sig in (frame.url or "").lower() for sig in ["captcha", "recaptcha", "hcaptcha", "turnstile"]):
                return True
    except Exception:
        pass
    return False


async def wait_for_captcha_resolution(page: Page):
    print("\n" + "=" * 55)
    print("  CAPTCHA_DETECTED")
    print("  Please solve the CAPTCHA in the browser window.")
    print("  Script will resume automatically once cleared.")
    print("=" * 55 + "\n")
    sys.stdout.flush()
    while True:
        await asyncio.sleep(CAPTCHA_POLL_SEC)
        if not await detect_captcha(page):
            print("  CAPTCHA resolved. Continuing...")
            sys.stdout.flush()
            await page.wait_for_timeout(1500)
            break


# --- PHASE 1: LAUNCH & NAVIGATE -----------------------------------------------

async def launch_and_navigate(url: str):
    """Opens a headed browser and navigates to the filtered career URL."""
    print(f"\n  >> Opening headed browser: {url}")
    sys.stdout.flush()

    pw = await async_playwright().start()

    # Try system Chrome first (most visible on Windows), fall back to bundled Chromium
    try:
        browser = await pw.chromium.launch(
            channel="chrome",      # Use installed system Chrome
            headless=False,
            slow_mo=50,
            args=["--start-maximized", "--focus-on-new-tab"]
        )
    except Exception:
        browser = await pw.chromium.launch(
            headless=False,
            slow_mo=50,
            args=["--start-maximized"]
        )

    context = await browser.new_context(
        no_viewport=True,          # Let the OS control window size (avoids hidden windows)
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
    )
    page = await context.new_page()
    await page.bring_to_front()    # Force window to foreground
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.bring_to_front()    # Bring to front again after navigation
    await page.wait_for_timeout(2000)

    if await detect_captcha(page):
        await wait_for_captcha_resolution(page)

    print("  >> Page loaded. Starting link harvest...")
    sys.stdout.flush()
    return pw, browser, context, page


# --- PHASE 2: HARVEST JOB LINKS -----------------------------------------------

async def harvest_links(page: Page) -> list[dict]:
    print("\n  --- Phase 2: Harvesting Links ---")
    all_jobs = []
    seen_hrefs = set()
    page_num = 0

    while page_num < MAX_PAGES:
        page_num += 1
        print(f"  >> Scanning listing page {page_num}...")
        sys.stdout.flush()

        if await detect_captcha(page):
            await wait_for_captcha_resolution(page)

        await auto_scroll(page)

        raw_links = await page.evaluate("""
            () => {
                const anchors = Array.from(document.querySelectorAll('a[href]'));
                return anchors.map(a => ({
                    href: a.href,
                    text: (a.innerText || a.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 150)
                })).filter(a => a.href && a.text.length > 3);
            }
        """)

        new_count = 0
        for link in raw_links:
            href = link["href"]
            if href not in seen_hrefs and is_job_link(href):
                seen_hrefs.add(href)
                all_jobs.append({"title": link["text"], "url": href, "description": ""})
                new_count += 1

        print(f"     +{new_count} new links (total so far: {len(all_jobs)})")
        sys.stdout.flush()

        went_next = await try_next_page(page)
        if not went_next:
            print("  >> No more listing pages.")
            break
        await page.wait_for_timeout(PAGE_LOAD_WAIT_MS)

    print(f"  >> Harvest done. {len(all_jobs)} unique job links found.")
    sys.stdout.flush()
    return all_jobs


def is_job_link(href: str) -> bool:
    href_lower = href.lower()
    job_kws  = ["/job/", "/jobs/", "/details/", "/position/", "/opening/",
                "/requisition/", "lever.co/", "greenhouse.io/", "workday.com/",
                "taleo.net/", "smartrecruiters.com/"]
    skip_kws = ["javascript:", "mailto:", "tel:", "linkedin.com/company",
                "twitter.com", "facebook.com", "instagram.com",
                "/about", "/contact", "/privacy", "/terms", "/login",
                "/blog", "/news", "/events", "/talentcommunity",
                "/categories", "/locations", "all/jobs?", "all/jobs#",
                "/hvhapply", "/jobcart", "/home", "/benefits", "/pilots",
                "/students", "/united-pathways", "/flight-attendant", "/military",
                "/search-results"]
    if any(s in href_lower for s in skip_kws):
        return False
    if href_lower.rstrip("/").endswith("/all/jobs") or href_lower.rstrip("/").endswith("/search"):
        return False
    return any(k in href_lower for k in job_kws)


async def auto_scroll(page: Page):
    await page.evaluate("""
        async () => {
            await new Promise(resolve => {
                let total = 0;
                const dist = 350;
                const t = setInterval(() => {
                    window.scrollBy(0, dist);
                    total += dist;
                    if (total >= document.body.scrollHeight - window.innerHeight) {
                        clearInterval(t); resolve();
                    }
                }, 120);
            });
        }
    """)
    await page.wait_for_timeout(SCROLL_PAUSE_MS)


async def try_next_page(page: Page) -> bool:
    selectors = [
        "button:has-text('Next')", "a:has-text('Next')",
        "[aria-label='Next page']", "[aria-label='Next']",
        "button:has-text('Load More')", "button:has-text('Show More')",
        ".pagination-next", ".next-page",
        "[data-ph-at-id='pagination-next']",
        "li.pagination__next a",
        "button[data-automation='pagination-next']",
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1000) and await btn.is_enabled():
                await btn.scroll_into_view_if_needed()
                await btn.click()
                return True
        except Exception:
            continue
    return False


# --- PHASE 3: PARALLEL PLAYWRIGHT TAB FETCH -----------------------------------

async def fetch_descriptions(jobs: list[dict], context: BrowserContext) -> list[dict]:
    """
    Opens up to PARALLEL_TAB_LIMIT browser tabs simultaneously.
    Each tab navigates to a job URL, waits for JS to render, then extracts text.
    Uses the same browser context (session/cookies shared).
    """
    print(f"\n  --- Phase 3: Headed Parallel Fetch ({len(jobs)} jobs, {PARALLEL_TAB_LIMIT} tabs) ---")
    sys.stdout.flush()

    semaphore = asyncio.Semaphore(PARALLEL_TAB_LIMIT)
    success_count = 0

    async def fetch_one(job: dict, idx: int):
        nonlocal success_count
        async with semaphore:
            tab = await context.new_page()
            try:
                # Use networkidle so JS-rendered SPAs (Phenom, Workday, etc.) fully hydrate
                # before we try to read content. domcontentloaded fires too early.
                try:
                    await tab.goto(job["url"], wait_until="networkidle", timeout=35000)
                except Exception:
                    # Fallback: some pages never fully reach networkidle; carry on anyway
                    pass

                # Wait for a content-bearing element to appear with real text.
                # Ordered from most-specific (Phenom ATS) to generic fallbacks.
                CONTENT_SELECTORS = [
                    "[data-ph-at-id='jobdetails-text']",   # Phenom ATS (UAL)
                    ".job-description",
                    ".job-details",
                    ".jd-info",
                    ".job-overview",
                    "[class*='job-desc']",
                    "[class*='jobdetail']",
                    ".description",
                ]
                found = False
                for sel in CONTENT_SELECTORS:
                    try:
                        await tab.wait_for_selector(sel, timeout=6000)
                        found = True
                        break
                    except Exception:
                        continue

                if not found:
                    # Generic fallback: poll until body text grows beyond boilerplate length
                    for _ in range(8):
                        await tab.wait_for_timeout(1000)
                        length = await tab.evaluate("() => document.body.innerText.length")
                        if length > 1500:
                            break
                else:
                    await tab.wait_for_timeout(1000)   # Small settle buffer after selector found

                if await detect_captcha(tab):
                    # Don't block on CAPTCHA inside description tabs — log and move on.
                    # CAPTCHA blocking only makes sense on the main listing page (Phase 1).
                    print(f"    [{idx+1}/{len(jobs)}] CAPTCHA on description tab — skipping wait, taking partial text")
                    sys.stdout.flush()

                # Extract visible text — works on any JS-rendered page
                text = await tab.evaluate("() => document.body.innerText")
                job["description"] = re.sub(r"\s+", " ", text).strip()[:8000]
                success_count += 1
                print(f"    [{idx+1}/{len(jobs)}] OK  {job['title'][:60]}")
            except Exception as e:
                job["description"] = f"[Error: {str(e)[:80]}]"
                print(f"    [{idx+1}/{len(jobs)}] ERR {job['url'][:60]}")
            finally:
                await tab.close()
            sys.stdout.flush()
        return job

    tasks = [fetch_one(job, i) for i, job in enumerate(jobs)]
    results = await asyncio.gather(*tasks)

    print(f"  >> Fetched {success_count}/{len(jobs)} descriptions successfully.")
    sys.stdout.flush()
    return list(results)


# --- PHASE 4: SAVE OUTPUT -----------------------------------------------------

def save_output(jobs: list[dict], company: str, output_file: str = "jobs_raw.json"):
    # Filter out non-job nav links that slipped through
    real_jobs = [j for j in jobs if j.get("description") and not j["description"].startswith("[Error")]

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    today = date.today().strftime("%Y-%m-%d")
    slug  = re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")
    base  = data_dir / f"{slug}_jobs_{today}"

    # Save timestamped JSON in data/
    json_path = base.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(real_jobs, f, indent=2, ensure_ascii=False)

    # Save to requested output_file (e.g., jobs_raw.json)
    raw_path = Path(output_file)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(real_jobs, f, indent=2, ensure_ascii=False)

    # Save CSV (title, url, description snippet)
    csv_path = base.with_suffix(".csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "url", "description"])
        writer.writeheader()
        for job in real_jobs:
            writer.writerow({
                "title":       job.get("title", ""),
                "url":         job.get("url", ""),
                "description": job.get("description", "")[:2000]   # trim for CSV readability
            })

    print(f"\n  >> Saved {len(real_jobs)} jobs:")
    print(f"       JSON     -> {raw_path.resolve()}")
    print(f"       Archive  -> {json_path.resolve()}")
    print(f"       CSV      -> {csv_path.resolve()}")
    print("  SCRAPE_COMPLETE")
    sys.stdout.flush()
    return str(raw_path)


# --- MAIN ---------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="AI Job Scraper -- Chat Controlled")
    parser.add_argument("--url",     required=True,  help="Filtered career page URL")
    parser.add_argument("--company", required=False, default="Company", help="Company name (used for output filename)")
    parser.add_argument("--output",  required=False, default="jobs_raw.json", help="Output JSON path (default: jobs_raw.json)")
    args = parser.parse_args()

    start = time.time()
    print("\n" + "=" * 55)
    print("  AI Job Scraper Started")
    print(f"  Company : {args.company}")
    print(f"  URL     : {args.url}")
    print("=" * 55)
    sys.stdout.flush()

    # Phase 1: Launch headed browser
    pw, browser, context, page = await launch_and_navigate(args.url)

    try:
        # Phase 2: Harvest all job links
        jobs = await harvest_links(page)

        if not jobs:
            print("\n  NO_JOBS_FOUND -- filters may be too strict or page did not load.")
            sys.stdout.flush()
            return

        # Phase 3: Fetch descriptions in parallel tabs
        jobs = await fetch_descriptions(jobs, context)

        # Phase 4: Save output immediately after fetch — before browser teardown
        # so a stuck/crashed browser never prevents data from being persisted.
        try:
            save_output(jobs, args.company, args.output)
        except Exception as save_err:
            print(f"  [WARN] Save failed: {save_err}")
            sys.stdout.flush()

    finally:
        try:
            for page in context.pages:
                try:
                    await page.close()
                except Exception:
                    pass
            await browser.close()
            await pw.stop()
        except Exception as e:
            print(f"  Browser shutdown notice: {e}")

    elapsed = time.time() - start
    print(f"  Total time: {elapsed:.1f}s for {len(jobs)} jobs\n")
    sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
