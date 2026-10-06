import json
import re
import sys

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def run():
    with open("jobs_raw.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    curated = []

    for job in data:
        title = job.get("title", "").strip()
        url = job.get("url", "").strip()
        desc = job.get("description", "")
        location = job.get("location", "").strip()

        if not location:
            loc_match = re.search(r'\b(Bengaluru|Bangalore|Gurugram|Gurgaon|Hyderabad|Chennai|Pune|Noida|Mumbai)\b', desc, re.I)
            location = loc_match.group(1).title() if loc_match else "India"

        lower_desc = desc.lower()

        # Isolate Basic Qualifications
        bq = ""
        if "basic qualifications" in lower_desc:
            bq_part = lower_desc.split("basic qualifications")[1]
            if "preferred qualifications" in bq_part:
                bq = bq_part.split("preferred qualifications")[0]
            else:
                bq = bq_part[:1200]
        else:
            bq = lower_desc

        # Filter out ANY positive experience requirement:
        # e.g., 1+ years, 2+ years, 6+ months, 1+ yrs, 3+ years, etc.
        has_positive_exp = False
        if re.search(r'(?:[1-9]\d*|\b6\b)\+?\s*(?:-|to)?\s*\d*\s*(?:years?|months?)(?:\s+of)?(?:\s+[a-z\s,-]{0,25})?\s*experience', bq):
            has_positive_exp = True
        if re.search(r'(?:at least\s+)?(?:[1-9]\d*)\s*(?:\+|or more)\s*years?', bq):
            has_positive_exp = True

        zero_explicit = re.search(r'\b0\s*(?:-|to)\s*(\d+)\s*(?:years?|months?)', bq)
        has_fresh_grad = bool(re.search(r'\b(?:fresh\s*grad(?:uate)?|no\s*experience\s*required|fresher)\b', bq))

        if has_positive_exp and not (zero_explicit or has_fresh_grad):
            continue

        if zero_explicit:
            exp_label = f"0-{zero_explicit.group(1)} mo/yr"
            match_type = "⭐⭐⭐ Strong"
        elif has_fresh_grad:
            exp_label = "0 YOE (Fresh Grad)"
            match_type = "⭐⭐⭐ Strong"
        else:
            exp_label = "0 YOE (No exp required)"
            match_type = "⭐⭐ Good"

        t_low = title.lower()
        if any(k in t_low for k in ["sde", "software", "system", "scientist", "ai", "machine learning", "cloud", "solutions architect", "developer"]):
            track = "Tech & Engineering"
        elif any(k in t_low for k in ["analyst", "data", "qa", "quality", "automation"]):
            track = "Data, QA & Analytics"
        else:
            track = "Operations & Business"

        curated.append({
            "title": title,
            "track": track,
            "location": location,
            "experience": exp_label,
            "match": match_type,
            "url": url,
            "bq": bq.strip()[:140].replace("\n", " ")
        })

    tech = [c for c in curated if c["track"] == "Tech & Engineering"]
    data_qa = [c for c in curated if c["track"] == "Data, QA & Analytics"]
    ops = [c for c in curated if c["track"] == "Operations & Business"]

    print(f"TECH_COUNT:{len(tech)}")
    for i, j in enumerate(tech, 1):
        print(f"T|{i}|{j['title']}|{j['location']}|{j['experience']}|{j['match']}|{j['url']}")

    print(f"DATA_COUNT:{len(data_qa)}")
    for i, j in enumerate(data_qa, 1):
        print(f"D|{i}|{j['title']}|{j['location']}|{j['experience']}|{j['match']}|{j['url']}")

    print(f"OPS_COUNT:{len(ops)}")
    for i, j in enumerate(ops[:10], 1):
        print(f"O|{i}|{j['title']}|{j['location']}|{j['experience']}|{j['match']}|{j['url']}")

if __name__ == "__main__":
    run()
