"""
find_url.py — ATS URL Resolver
================================
Run before scraper.py to find the correct filtered career URL for a company.

Usage:
    python find_url.py --company "EXL Service" --slug exlservice
    python find_url.py --company "McKinsey" --slug mckinsey --location "Gurugram"

What it does:
    1. Generates candidate ATS URLs from the company slug
    2. Fires HEAD requests in parallel (fast, no body download)
    3. Falls back to GET + body scan on any 200 hits (catches soft-404s)
    4. Prints a ranked confidence table
    5. Outputs the best URL as a single line at the end (for the agent to parse)
"""

import argparse
import asyncio
import re
import sys
import urllib.parse
from dataclasses import dataclass

import aiohttp

# Fix Windows console encoding (CP1252 can't print emoji)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# ATS URL TEMPLATES
# Each entry: (ats_name, url_template)
# {slug}      = slugified company name  (e.g. "exlservice")
# {slug_dash} = dash-separated slug     (e.g. "exl-service")
# ---------------------------------------------------------------------------

ATS_TEMPLATES = [
    # Eightfold AI
    ("Eightfold",       "https://jobs.{slug}.com/"),
    ("Eightfold",       "https://careers.{slug}.com/"),

    # Phenom ATS
    ("Phenom",          "https://jobs.{slug}.com/all/jobs"),
    ("Phenom",          "https://jobs.{slug_dash}.com/all/jobs"),

    # Workday (common tenant patterns)
    ("Workday",         "https://{slug}.wd5.myworkdayjobs.com/"),
    ("Workday",         "https://{slug}.wd1.myworkdayjobs.com/"),
    ("Workday",         "https://{slug}.wd3.myworkdayjobs.com/"),

    # Greenhouse
    ("Greenhouse",      "https://boards.greenhouse.io/{slug}"),
    ("Greenhouse",      "https://boards.greenhouse.io/{slug_dash}"),

    # Lever
    ("Lever",           "https://jobs.lever.co/{slug}"),
    ("Lever",           "https://jobs.lever.co/{slug_dash}"),

    # SmartRecruiters
    ("SmartRecruiters", "https://careers.smartrecruiters.com/{slug}"),

    # iCIMS
    ("iCIMS",           "https://careers.icims.com/jobs/search?pr_&in_iframe=1&hashed=-625985159&mobile=false&width=1140&height=500&bga=true&needsRedirect=false&jan1offset=330&jun1offset=330"),

    # Taleo
    ("Taleo",           "https://{slug}.taleo.net/careersection/jobsearch.ftl"),

    # Generic /careers or /jobs subpath
    ("Generic",         "https://www.{slug}.com/careers"),
    ("Generic",         "https://www.{slug}.com/jobs"),
    ("Generic",         "https://{slug}.com/careers"),
]

# Body keywords that STRONGLY confirm a real careers page (need 2+ or a strong one)
POSITIVE_KW_STRONG = ["view all jobs", "search jobs", "job openings", "open positions",
                       "apply now", "job listings", "current openings", "explore opportunities"]
POSITIVE_KW_WEAK   = ["career", "apply", "position", "opening", "vacancy", "hiring"]
# Body keywords that indicate a dead/wrong page
NEGATIVE_KW = ["page not found", "404", "doesn't exist", "no longer available",
               "this page cannot be found", "nothing here", "no jobs found",
               "no results", "0 jobs", "no open positions"]
# SmartRecruiters returns 200 for ANY slug; detect their empty-company page
SMARTRECRUITERS_EMPTY = ["there are currently no job openings", "no open positions at this time",
                          "smartrecruiters.com" and "no jobs"]

TIMEOUT = aiohttp.ClientTimeout(total=8)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )
}


@dataclass
class Result:
    ats: str
    url: str
    status: int
    confidence: str   # HIGH / MEDIUM / LOW / DEAD
    note: str
    final_url: str = ""


async def ping(session: aiohttp.ClientSession, ats: str, url: str) -> Result:
    """
    Step 1: HEAD request.
    Step 2: If 200/301/302, do a GET and scan body.
    """
    try:
        async with session.head(url, allow_redirects=True, timeout=TIMEOUT) as resp:
            status = resp.status
            final_url = str(resp.url)

            # Definite dead
            if status == 404:
                return Result(ats, url, status, "DEAD", "404 Not Found", final_url)

            # Redirect to a completely different domain = probably homepage catch-all
            if status in (301, 302):
                parsed_orig = urllib.parse.urlparse(url).netloc
                parsed_final = urllib.parse.urlparse(final_url).netloc
                if parsed_orig not in parsed_final and parsed_final not in parsed_orig:
                    return Result(ats, url, status, "LOW",
                                  f"Redirected to different domain: {parsed_final}", final_url)

            if status not in (200, 301, 302, 403):
                return Result(ats, url, status, "LOW", f"HTTP {status}", final_url)

    except Exception as e:
        return Result(ats, url, 0, "DEAD", f"Connection error: {str(e)[:60]}")

    # Step 2: GET + body scan (only for 200/301/302)
    if status == 403:
        return Result(ats, url, status, "MEDIUM",
                      "403 — real URL but blocking bots; try in browser", final_url)

    try:
        async with session.get(url, allow_redirects=True, timeout=TIMEOUT) as resp:
            body = (await resp.text(errors="replace"))[:5000].lower()
            final_url = str(resp.url)

            has_negative = any(kw in body for kw in NEGATIVE_KW)
            has_strong   = any(kw in body for kw in POSITIVE_KW_STRONG)
            weak_hits    = sum(1 for kw in POSITIVE_KW_WEAK if kw in body)

            # SmartRecruiters-specific: returns 200 for any slug, check for real listings
            is_smartrecruiters = "smartrecruiters.com" in final_url.lower()
            if is_smartrecruiters:
                # SR empty-company pages say "no job openings" or have very little content
                if any(kw in body for kw in ["no job openings", "no open positions", "no positions"]):
                    return Result(ats, url, status, "DEAD",
                                  "SmartRecruiters: company has no active listings", final_url)
                if not has_strong and weak_hits < 3:
                    return Result(ats, url, status, "MEDIUM",
                                  "SmartRecruiters: 200 OK but could not confirm active listings", final_url)

            if has_negative:
                return Result(ats, url, status, "DEAD", "Soft 404 detected in body", final_url)
            if has_strong:
                return Result(ats, url, status, "HIGH", "Body confirms careers page (strong signal)", final_url)
            if weak_hits >= 2:
                return Result(ats, url, status, "MEDIUM", f"Body has {weak_hits} careers keywords (weak signal)", final_url)
            return Result(ats, url, status, "LOW", "200 OK but no careers content detected", final_url)

    except Exception as e:
        return Result(ats, url, status, "MEDIUM",
                      f"HEAD OK but GET failed: {str(e)[:60]}", final_url)


async def resolve(slug: str, slug_dash: str) -> list[Result]:
    candidates = []
    seen = set()
    for ats, template in ATS_TEMPLATES:
        url = template.format(slug=slug, slug_dash=slug_dash)
        if url not in seen:
            seen.add(url)
            candidates.append((ats, url))

    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:
        tasks = [ping(session, ats, url) for ats, url in candidates]
        results = await asyncio.gather(*tasks)

    return list(results)


def rank(results: list[Result]) -> list[Result]:
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "DEAD": 3}
    return sorted(results, key=lambda r: (order.get(r.confidence, 4), r.url))


def print_table(results: list[Result], company: str):
    CONF_ICON = {"HIGH": "[OK]", "MEDIUM": "[??]", "LOW": "[LO]", "DEAD": "[XX]"}
    print(f"\n{'='*70}")
    print(f"  ATS URL Resolver — {company}")
    print(f"{'='*70}")
    print(f"  {'CONF':<8} {'ATS':<16} {'STATUS':<8} {'URL'}")
    print(f"  {'-'*66}")
    for r in results:
        icon = CONF_ICON.get(r.confidence, "?")
        status_str = str(r.status) if r.status else "ERR"
        url_display = r.final_url if r.final_url and r.final_url != r.url else r.url
        print(f"  {icon} {r.confidence:<6} {r.ats:<16} {status_str:<8} {url_display[:60]}")
        if r.note:
            print(f"           {'':<16}          {r.note}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Resolve the correct ATS careers URL for a company")
    parser.add_argument("--company", required=True,  help="Company display name (e.g. 'EXL Service')")
    parser.add_argument("--slug",    required=False, help="URL slug (e.g. 'exlservice'). Auto-derived if omitted.")
    parser.add_argument("--location",required=False, default="India", help="Location hint (informational)")
    parser.add_argument("--best",    action="store_true", help="Print only the best URL (for agent parsing)")
    args = parser.parse_args()

    # Derive slug from company name if not provided
    slug      = args.slug or re.sub(r"[^a-z0-9]", "", args.company.lower())
    slug_dash = args.slug or re.sub(r"[^a-z0-9]+", "-", args.company.lower()).strip("-")

    print(f"\n  Resolving ATS URL for: {args.company}")
    print(f"  Slug: {slug} / {slug_dash}")
    print(f"  Location hint: {args.location}")
    print(f"  Pinging {len(ATS_TEMPLATES)} candidate URLs in parallel...\n")

    results = asyncio.run(resolve(slug, slug_dash))
    ranked  = rank(results)

    if args.best:
        # Just print the top HIGH confidence URL for agent parsing
        for r in ranked:
            if r.confidence == "HIGH":
                print(r.final_url or r.url)
                return
        # Fallback: MEDIUM
        for r in ranked:
            if r.confidence == "MEDIUM":
                print(r.final_url or r.url)
                return
        print("NO_URL_FOUND")
    else:
        print_table(ranked, args.company)
        # Always print the best pick at the end for easy reading
        top = ranked[0]
        if top.confidence in ("HIGH", "MEDIUM"):
            print(f"  >> BEST PICK: [{top.confidence}] {top.ats}")
            print(f"     {top.final_url or top.url}")
            print(f"\n  Pass this URL to scraper.py --url \"<url>\"")
        else:
            print("  >> No confident URL found. Use the base company careers page")
            print("     and set filters manually in the headed browser.")
        print()


if __name__ == "__main__":
    main()
