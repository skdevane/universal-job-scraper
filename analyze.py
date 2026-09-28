"""
Job Analyzer — AI-Powered, Chat-Controlled
==========================================
Reads jobs_raw.json and extracts EXACT experience requirements
from the description text. Never infers from job title.

Usage:
    python analyze.py [--input jobs_raw.json] [--max-yoe 2]
"""

import json
import re
import argparse
import sys
from datetime import date
from pathlib import Path

# Force UTF-8 output on Windows to handle emoji in markdown
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# EXPERIENCE EXTRACTION
# ---------------------------------------------------------------------------

def extract_experience(description: str) -> tuple:
    """
    Returns (yoe_min, yoe_max, label).
    yoe_max=99 means open-ended (e.g. '3+ years').
    Returns (-1, -1, 'Unknown') if no pattern matched.
    """
    text = description.lower()
    # Normalize unicode hyphens/dashes to standard ASCII hyphen
    text = re.sub(r'[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]', '-', text)

    # UAL Phenom ATS format: "Experience: 1+ year"
    m = re.search(r'experience:\s*(\d+)\s*\+?\s*years?', text)
    if m:
        n = int(m.group(1))
        return (n, 99, f"{n}+ yr")

    # 1) Range starting with 0 (e.g. 0-1 yr, 0-2 yrs, 0-3+ yrs, 0 to 3 years)
    m = re.search(r'\b0\s*(?:-|to|\bto\b)\s*(\d+)\s*\+?\s*years?', text)
    if m:
        max_yoe = int(m.group(1))
        return (0, max_yoe, f"0-{max_yoe} yrs")

    # 2) Fresh grad / entry level / no experience
    if re.search(r'\b(?:no experience required|entry[- ]level|fresh\s*grad|fresher)\b', text):
        return (0, 1, "0-1 yr")

    # 3) Month ranges (e.g., 6 months - 2 years)
    if re.search(r'6\s*months?\s*-\s*2\s*years?', text) or re.search(r'at least\s+6\s+months?', text):
        return (0, 2, "6mo-2 yrs")

    # 4) Any general range: N1 - N2 years (e.g. 1-3, 3-6, 5-8, 8-10, 10-15, 3-5+ years)
    m = re.search(r'\b(\d+)\s*(?:-|to|\bto\b)\s*(\d+)\s*\+?\s*years?', text)
    if m:
        min_yoe = int(m.group(1))
        max_yoe = int(m.group(2))
        return (min_yoe, max_yoe, f"{min_yoe}-{max_yoe} yrs")

    # 5) Open ended: N+ years or at least N years or N or more years
    m = re.search(r'(?:at least\s+)?\b(\d+)\s*(?:\+|\s+or\s+more)\s*years?', text)
    if m:
        n = int(m.group(1))
        return (n, 99, f"{n}+ yrs")

    # 6) Single year requirement (e.g. "2 years of experience", "2 years of information systems experience")
    m = re.search(r'\b(\d+)\s*\+?\s*years?\s*(?:of\s*)?(?:[a-z\s,-]{0,35})?experience\b', text)
    if m:
        n = int(m.group(1))
        return (n, n, f"{n} yrs")

    # Catch-all N+ year
    m = re.search(r'\b(\d+)\s*\+\s*years?', text)
    if m:
        n = int(m.group(1))
        return (n, 99, f"{n}+ yrs")

    return (-1, -1, "Unknown")


# ---------------------------------------------------------------------------
# MATCH SCORING
# ---------------------------------------------------------------------------

def match_score(yoe_min: int, yoe_max: int, target_max: int) -> tuple:
    if yoe_min == -1:
        return ("?", "Unknown exp")
    if yoe_min == 0:
        return ("Strong", "Strong")
    if yoe_min <= target_max:
        return ("Good", "Good")
    return ("Weak", "Weak")


# ---------------------------------------------------------------------------
# CATEGORY DETECTION
# ---------------------------------------------------------------------------

TECH_KW = [
    "engineer", "developer", "software", "cloud", "devops", "data scientist",
    "machine learning", "ai engineer", "cybersecurity", "architect", "technology",
    "digital", "it appl", "analytics",
]

def is_tech(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in TECH_KW)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def analyze(input_path: str, max_yoe: int, save_md: bool):
    data = json.load(open(input_path, encoding="utf-8"))
    results = []

    for job in data:
        title = job.get("title", "")
        url   = job.get("url", "")
        desc  = job.get("description", "")

        # Extract real title if title is a placeholder like 'Job 1', 'Job 2', or empty
        if not title or re.match(r'^Job\s+\d+$', title, re.IGNORECASE):
            # Try Eightfold pattern: 'View More Jobs <Title> <Location> Apply Now'
            tm = re.search(r'(?:View More Jobs\s+|Jobs\s+)([A-Za-z0-9\s\-/&,\(\)\.\+]+?)\s+([A-Za-z\s,]+(?:India|Spain|United States|UK|London|Bengaluru|Gurgaon|Gurugram|Noida|Pune|Hyderabad|Chennai|Hybrid|Remote)[^\n\r]*?)\s+Apply Now', desc)
            if tm:
                title = tm.group(1).strip()
            else:
                # Try before 'Apply Now' or 'JOB DESCRIPTION'
                tm2 = re.search(r'(?:^|\n)([A-Z][A-Za-z0-9\s\-/&,\(\)\.\+]{4,60})\s+(?:Apply Now|JOB DESCRIPTION)', desc)
                if tm2:
                    title = tm2.group(1).strip()

        # Clean title artifacts
        title = re.sub(r'^(?:Skip to main content\.?\s*)?(?:About Team Amex\s*)?(?:Career Areas\s*)?(?:Locations\s*)?(?:Students\s*)?(?:Jobs\s*)?(?:American English\s*)?(?:View More Jobs\s*)+', '', title, flags=re.IGNORECASE).strip()
        title = re.sub(r'\s*-\s*$', '', title).strip()
        if not title or title.lower() in ["american", "american english", "jobs"]:
            # Fallback search inside desc
            fb = re.search(r'View More Jobs\s+([A-Za-z0-9\s\-/&,\(\)\.\+]+?)(?:\s+Bengaluru|\s+Gurgaon|\s+Gurugram|\s+Noida|\s+Pune|\s+Mumbai|\s+Hyderabad|\s+Chennai|\s+India|\s+Apply Now)', desc, re.IGNORECASE)
            if fb:
                title = fb.group(1).strip()
            else:
                title = job.get("title", "Job")

        # Extract location
        loc_m = re.search(r'Location\s+([^\n]+?(?:India|Haryana|Maharashtra|Karnataka|Bengaluru|Gurgaon|Gurugram|Pune|Noida|Hyderabad|Chennai)[^\n]*)', desc, re.IGNORECASE)
        if not loc_m:
            loc_m = re.search(r'\b(Bengaluru|Gurgaon|Gurugram|Noida|Pune|Mumbai|Hyderabad|Chennai|Delhi|India)\b[^\n\r]*?(?:India)?', desc, re.IGNORECASE)

        if loc_m:
            loc_str = loc_m.group(0) if loc_m.lastindex == 0 else loc_m.group(1)
            location = (loc_str.strip()
                        .replace("Gurugram, Haryana, India", "Gurgaon")
                        .replace("Gurugram", "Gurgaon")
                        .replace("Mumbai, Maharashtra, India", "Mumbai")
                        .replace("Pune, Maharashtra, India", "Pune")
                        .replace("Bengaluru, Karnataka, India", "Bengaluru")
                        .replace("Karnataka, India", "Bengaluru")
                        .replace("Haryana, India", "Gurgaon"))
            # Keep clean city name
            for city in ["Bengaluru", "Gurgaon", "Pune", "Mumbai", "Hyderabad", "Noida", "Chennai", "India"]:
                if city.lower() in location.lower():
                    location = city
                    break
        else:
            location = "India"

        # Extract posted date
        date_m = re.search(r'Posted Date\s+([\d/]+)', desc)
        posted = date_m.group(1) if date_m else "Recent"

        yoe_min, yoe_max, yoe_label = extract_experience(desc)
        stars_word, label = match_score(yoe_min, yoe_max, max_yoe)
        stars = {"Strong": "Strong", "Good": "Good", "Weak": "Weak", "Unknown exp": "?"}.get(stars_word, "?")
        category = "Tech" if is_tech(title) or is_tech(desc[:500]) else "Non-Tech"

        results.append({
            "title": title, "url": url, "location": location,
            "yoe_min": yoe_min, "yoe_max": yoe_max, "yoe_label": yoe_label,
            "posted": posted, "stars": stars, "label": label, "category": category,
        })

    # Sort: Strong first, then yoe_min ascending
    order = {"Strong": 0, "Good": 1, "Weak": 2, "?": 3}
    results.sort(key=lambda r: (order.get(r["stars"], 3), r["yoe_min"]))

    # --- Console output ---
    STARS = {"Strong": "⭐⭐⭐", "Good": "⭐⭐", "Weak": "⭐", "?": "❓"}

    print(f"\n{'='*70}")
    print(f"  Job Analysis — {date.today()} | {input_path} | max YOE: {max_yoe}")
    print(f"  Total jobs: {len(results)}")
    print(f"{'='*70}\n")

    for cat in ["Tech", "Non-Tech"]:
        cat_jobs = [r for r in results if r["category"] == cat]
        icon = "💻" if cat == "Tech" else "💼"
        print(f"{'='*10} {icon} {cat} Roles {'='*10}")
        print(f"{'#':<3} {'Title':<50} {'Location':<12} {'Exp':<14} {'Posted':<12} {'Match'}")
        print("-" * 110)
        for i, r in enumerate(cat_jobs, 1):
            match_str = f"{STARS.get(r['stars'], '?')} {r['label']}"
            print(f"{i:<3} {r['title'][:48]:<50} {r['location'][:11]:<12} {r['yoe_label']:<14} {r['posted']:<12} {match_str}")
            print(f"    {r['url']}")
        print()

    # --- Markdown output ---
    if save_md:
        out_dir = Path("data")
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"analysis_{date.today()}.md"
        lines = [
            f"# Job Analysis — {date.today()}\n\n",
            f"**Source**: `{input_path}` | **Max YOE filter**: {max_yoe}\n\n",
        ]
        for cat in ["Tech", "Non-Tech"]:
            cat_jobs = [r for r in results if r["category"] == cat]
            icon = "💻" if cat == "Tech" else "💼"
            lines.append(f"## {icon} {cat} Roles\n\n")
            lines.append("| # | Title | Location | Experience | Posted | Match | Apply |\n")
            lines.append("|---|-------|----------|------------|--------|-------|-------|\n")
            for i, r in enumerate(cat_jobs, 1):
                match_str = f"{STARS.get(r['stars'], '?')} {r['label']}"
                lines.append(
                    f"| {i} | **{r['title']}** | {r['location']} | {r['yoe_label']} "
                    f"| {r['posted']} | {match_str} | [Apply]({r['url']}) |\n"
                )
            lines.append("\n")
        out_path.write_text("".join(lines), encoding="utf-8")
        print(f"  >> Markdown saved -> {out_path.resolve()}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze scraped jobs from jobs_raw.json")
    parser.add_argument("--input",   default="jobs_raw.json", help="Path to jobs JSON")
    parser.add_argument("--max-yoe", type=int, default=2,     help="Max YOE to highlight (default: 2)")
    parser.add_argument("--no-md",   action="store_true",     help="Skip markdown save")
    args = parser.parse_args()
    analyze(args.input, args.max_yoe, not args.no_md)
