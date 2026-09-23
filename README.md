# 🤖 Universal Job Scraper — AI-Controlled

> You talk to the AI in chat. The AI does everything — runs the scraper, monitors for CAPTCHAs, reads the output, and reports matching jobs to you in a table. You never touch the terminal.

---

## How It Works

```
You (chat) ──► AI constructs filtered URL
                   │
               Runs scraper.py (background)
                   │
         Headed browser opens on your screen
                   │
          [If CAPTCHA] → AI alerts you in chat
          You solve it → script auto-resumes
                   │
          Sweeps all listing pages (paginated)
                   │
       Fetches all job descriptions in parallel
       (up to 5 tabs simultaneously)
                   │
       Saves → jobs_raw.json + data/<company>_jobs_<date>.json/.csv
                   │
          AI reads file → runs analyze.py
                   │
     Posts ranked match table to chat (with Apply links)
```

---

## The Phases (all automatic)

| Phase | What Happens | Who Does It |
|-------|-------------|-------------|
| 1 | Browser opens, navigates to filtered career URL | **Script** |
| 2 | Detects CAPTCHA → pauses, notifies you in chat | **Script + You** |
| 3 | Sweeps all pages, harvests job links | **Script** |
| 4 | Parallel tabs fetch JS-rendered job descriptions | **Script** |
| 5 | AI reads output, matches against your criteria, reports table | **AI** |

---

## Setup (One-Time)

Python 3.10+ required.

```bash
pip install -r requirements.txt
playwright install chromium
```

---

## Usage — Just Talk to the AI

Tell the AI what you want in chat:

> *"Search ZS Careers India for fresher data analytics or software roles, 0–2 years max."*

The AI will:
1. Construct the best filtered URL for that company
2. Run `scraper.py` as a background task
3. Watch the log for `CAPTCHA_DETECTED` and alert you if needed
4. After `SCRAPE_COMPLETE`, run `analyze.py` and post a result table

---

## Output Format

The AI always reports results in this table:

| # | Job Title | Location | Experience | Posted Date | Match | Apply |
|---|-----------|----------|------------|-------------|-------|-------|
| 1 | Decision Analytics Associate | Pune | 0–2 yrs | 3 days ago | ⭐⭐⭐ Strong | [Apply](url) |
| 2 | Business Technology Associate | Gurgaon | Fresh grad | Recent | ⭐⭐ Good | [Apply](url) |

**Match scoring:**
- ⭐⭐⭐ **Strong** — 0 yrs / entry-level / fresh grad / no experience required
- ⭐⭐ **Good** — Meets most criteria, minor gap
- ⭐ **Weak** — Partial match (reason noted)
- ❓ — Experience requirement not found in description text

> **Note:** Experience is always extracted directly from description text — never inferred from the job title.

---

## Output Files

After each run, the scraper saves to three places:

```
jobs_raw.json                          ← Latest run (always overwritten)
data/<company>_jobs_<date>.json        ← Timestamped archive
data/<company>_jobs_<date>.csv         ← CSV version for spreadsheets
data/analysis_<date>.md               ← Markdown analysis table (from analyze.py)
```

### JSON schema

```json
[
  {
    "title": "Decision Analytics Associate",
    "url": "https://jobs.zs.com/all/jobs/12345",
    "description": "ZS is looking for... 0-2 years of experience..."
  }
]
```

---

## Files

```
universal-job-scraper/
├── scraper.py          ← Main scraper (Playwright, async, headed browser)
├── analyze.py          ← Post-scrape analyzer (extracts YOE, scores matches, saves markdown)
├── launch.py           ← Windows launcher (spawns scraper in visible console, tails log)
├── requirements.txt    ← playwright>=1.44.0, aiohttp>=3.9.0
├── jobs_raw.json       ← Output from latest scrape
├── scraper_output.log  ← Live log tailed by AI during scrape
├── AGENTS.md           ← AI agent behavior rules (how the AI operates this workspace)
└── data/               ← Timestamped archives (JSON, CSV, markdown analysis)
```

---

## Supported Sites

The scraper is **DOM-agnostic** — it uses JavaScript to harvest all `<a href>` links matching job URL patterns, so it works across different ATS platforms:

| ATS / Platform | Notes |
|---------------|-------|
| **Phenom ATS** (ZS, United Airlines, etc.) | Full SPA support, `networkidle` wait |
| **Workday** | Standard job URL pattern matched |
| **Greenhouse** | `greenhouse.io` links matched |
| **Lever** | `lever.co` links matched |
| **SmartRecruiters** | `smartrecruiters.com` links matched |
| **Taleo** | `taleo.net` links matched |
| Any other site | Generic fallback via body text polling |

---

## Known Site-Specific Behavior

### United Airlines (careers.united.com — Phenom ATS)
- Fully JS-rendered SPA — uses `networkidle` + body text length polling
- CAPTCHA may appear on description tabs — logged and skipped (data still saved)
- Experience format: `"Experience: 1+ year"` in body text

### ZS Careers (jobs.zs.com)
- Standard Phenom ATS, loads reliably
- No login wall on job detail pages
- Best URL: `https://jobs.zs.com/all/jobs?location=India&woe=12&regionCode=IN`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No jobs found | Filters may be too strict, or the page didn't fully load |
| Jobs blocked (403 on descriptions) | Script falls back to partial text — still saves what it gets |
| CAPTCHA | Solve it in the browser — AI will tell you in chat. Script resumes automatically |
| `playwright` not found | Run `playwright install chromium` |
| Browser doesn't appear | Try running `launch.py` directly — it forces a visible Windows console |

---

## Manual Usage (without AI)

You can also run the scripts directly:

```bash
# Scrape a company
python scraper.py --url "https://jobs.zs.com/all/jobs?location=India&woe=12&regionCode=IN" --company "ZS"

# Analyze results
python analyze.py --input jobs_raw.json --max-yoe 2

# Or use the Windows launcher (shows browser + tails log)
python launch.py --url "https://jobs.zs.com/all/jobs" --company "ZS"
```

```bash
# Other companies
python scraper.py --url "https://www.mckinsey.com/careers/search-jobs" --company "McKinsey"
python scraper.py --url "https://apply.deloitte.com/careers/SearchJobs" --company "Deloitte"
```

---

## Default Behavior (AI-controlled mode)

| Setting | Default |
|---------|---------|
| Location | **India** (Gurgaon, Pune, Bengaluru, Hyderabad, Noida, Chennai) |
| Experience target | **Fresher / 0–2 years** |
| Parallel tabs | 5 simultaneous |
| Max pages | 30 (safety cap) |
| Description cap | 8000 chars per job |
