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

    # UAL Phenom ATS format: "Experience: 1+ year"
    m = re.search(r'experience:\s*(\d+)\s*\+?\s*year', text)
    if m:
        n = int(m.group(1))
        return (n, 99, f"{n}+ yr")

    patterns = [
        (r'\bno experience required\b',                      (0, 0,  "No exp required")),
        (r'\bentry[- ]level\b',                               (0, 1,  "Entry level")),
        (r'\bfresh\s*grad',                                   (0, 0,  "Fresh grad")),
        (r'\b0\s*[-to]+\s*1\s*year',                          (0, 1,  "0-1 yr")),
        (r'\b0\s*[-to]+\s*2\s*year',                          (0, 2,  "0-2 yrs")),
        (r'\b0\s*[-to]+\s*3\s*year',                          (0, 3,  "0-3 yrs")),
        (r'at least\s+6\s+months?\s*[-]+\s*2\s+year',        (0, 2,  "6mo-2 yrs")),
        (r'6\s+months?\s*[-]+\s*2\s+year',                   (0, 2,  "6mo-2 yrs")),
        (r'\b1\s*[-to]+\s*2\s*year',                          (1, 2,  "1-2 yrs")),
        (r'\b1\s*[-to]+\s*3\s*year',                          (1, 3,  "1-3 yrs")),
        (r'(?:at least\s+)?1\s*\+\s*year',                    (1, 99, "1+ yr")),
        (r'\b1\s+or\s+more\s+year',                           (1, 99, "1+ yr")),
        (r'(?:at least\s+)?2\s*\+\s*year',                    (2, 99, "2+ yrs")),
        (r'\b2\s+or\s+more\s+year',                           (2, 99, "2+ yrs")),
        (r'\b2\s*[-to]+\s*3\s*year',                          (2, 3,  "2-3 yrs")),
        (r'\b2\s*[-to]+\s*4\s*year',                          (2, 4,  "2-4 yrs")),
        (r'at least\s+2\s+year',                              (2, 99, "2+ yrs")),
        (r'(?:at least\s+)?3\s*\+\s*year',                    (3, 99, "3+ yrs")),
        (r'\b3\s*[-to]+\s*5\s*year',                          (3, 5,  "3-5 yrs")),
        (r'(?:at least\s+)?5\s*\+\s*year',                    (5, 99, "5+ yrs")),
        (r'(?:at least\s+)?6\s*\+\s*year',                    (6, 99, "6+ yrs")),
    ]

    for pattern, result in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return result

    # Catch any "N+ years" we might have missed
    m = re.search(r'\b(\d+)\s*\+\s*year', text)
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
        title = job["title"]
        url   = job["url"]
        desc  = job.get("description", "")

        # Extract location
        loc_m = re.search(r'Location\s+([^\n]+?(?:India|Haryana|Maharashtra|Karnataka)[^\n]*)', desc)
        location = loc_m.group(1).strip() if loc_m else "India"
        location = (location
                    .replace("Gurugram, Haryana, India", "Gurgaon")
                    .replace("Mumbai, Maharashtra, India", "Mumbai")
                    .replace("Pune, Maharashtra, India", "Pune")
                    .replace("Bengaluru, Karnataka, India", "Bengaluru"))

        # Extract posted date
        date_m = re.search(r'Posted Date\s+([\d/]+)', desc)
        posted = date_m.group(1) if date_m else "Recent"

        yoe_min, yoe_max, yoe_label = extract_experience(desc)
        stars_word, label = match_score(yoe_min, yoe_max, max_yoe)
        stars = {"Strong": "Strong", "Good": "Good", "Weak": "Weak", "Unknown exp": "?"}.get(stars_word, "?")
        category = "Tech" if is_tech(title) else "Non-Tech"

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
