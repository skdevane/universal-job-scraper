# 🤖 Universal Job Scraper - AI-Controlled

> You talk to the AI in chat. The AI does everything - runs the scraper, monitors for CAPTCHAs, reads the output, and reports matching jobs to you in a table. You never touch the terminal.

---

## How It Works

```
You (chat) ──► AI constructs filtered URL
                   │
               Runs scraper.py (background)
                   │
         Headed browser opens on your screen
                   │
           Rejects all cookies automatically
           (accepts only if no reject option)
                   │
         Waits for job cards to render in DOM
         (SPA-safe: Eightfold, Phenom, Workday)
                   │
          [If CAPTCHA] → AI alerts you in chat
          You solve it → script auto-resumes
                   │
          Sweeps all listing pages
          (Next / Load More / Show More Results)
                   │
       [If 0 jobs] → [DIAG] dump auto-fires
       AI reads it → fixes URL pattern → re-runs
       (no browser inspection needed)
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
| 2 | Rejects all cookies (accepts if no reject option) | **Script** |
| 3 | Waits for job cards to hydrate in DOM (SPA-safe) | **Script** |
| 4 | Detects CAPTCHA → pauses, notifies you in chat | **Script + You** |
| 5 | Sweeps all pages, harvests job links | **Script** |
| 6 | If 0 links: `[DIAG]` dump fires, AI fixes & re-runs | **Script + AI** |
| 7 | Parallel tabs fetch JS-rendered job descriptions | **Script** |
| 8 | AI reads output, matches against your criteria, reports table | **AI** |

---

## Setup (One-Time)

Python 3.10+ required.

```bash
pip install -r requirements.txt
playwright install chromium
```

---

## Usage - Just Talk to the AI

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
- ⭐⭐⭐ **Strong** - 0 yrs / entry-level / fresh grad / no experience required
- ⭐⭐ **Good** - Meets most criteria, minor gap
- ⭐ **Weak** - Partial match (reason noted)
- ❓ - Experience requirement not found in description text

> **Note:** Experience is always extracted directly from description text - never inferred from the job title.

---

## Output Files

After each run, the scraper and analyzer save to:

```
jobs_raw.json                          ← Latest run raw scrape (overwritten each run)
data/<company>_jobs_<date>.json        ← Timestamped raw JSON archive
data/<company>_jobs_<date>.csv         ← CSV version for spreadsheet analysis
data/analysis_<date>.md               ← Full ranked markdown analysis (optional via --no-md)
```

### Why the Analysis Markdown Report (`analysis_<date>.md`)?
- **Full Catalog**: While the chat summary shows the top 10–15 curated matches, the `.md` report contains the exhaustive list of all scraped jobs (e.g. 300+ jobs) with direct apply links.
- **Offline Reference**: Accessible anytime in your IDE or markdown viewer with `Ctrl+F` search capability.
- **Diffing & History**: Dated filenames allow tracking new job openings week-over-week.
- **Optional**: Pass `--no-md` to `analyze.py` if you only want the terminal/chat output without saving a file.

### JSON Schema

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
├── scraper.py          ← Main scraper (Playwright, async, headed browser, Shadow DOM support)
├── find_url.py         ← ATS URL resolver (checks cache first, then pings candidate ATS endpoints)
├── company_urls.csv    ← Verified URL cache + site-specific quirks (updated post-scrape)
├── analyze.py          ← Post-scrape analyzer (extracts exact YOE, scores matches, generates markdown)
├── launch.py           ← Windows launcher (spawns scraper in visible console, tails log)
├── requirements.txt    ← playwright>=1.44.0, aiohttp>=3.9.0
├── jobs_raw.json       ← Output from latest scrape
├── scraper_output.log  ← Live log tailed during scraping runs
├── AGENTS.md           ← AI agent behavior rules and execution workflows
└── data/               ← Timestamped archives (JSON, CSV, markdown analysis)
```

---

## Supported Sites & ATS Engines

The scraper is **DOM-agnostic** — it harvests all links matching job URL patterns, waits for SPA hydration, pierces Shadow DOM boundaries, and self-diagnoses on failure:

| ATS / Platform | Capabilities & Notes |
|---------------|----------------------|
| **Amazon Jobs** (`amazon.jobs`) | Custom portal, paginated `/en/jobs/<ID>/<slug>` matching |
| **Eightfold ATS** (American Express, etc.) | Shadow DOM piercing via Playwright locators; cookie reject; "Show More Results" pagination |
| **Phenom ATS** (ZS, United Airlines, etc.) | Full SPA support, `networkidle` wait, body innerText polling |
| **Oracle HCM** (EXL Service, Oracle Cloud) | Custom tenant subdomains, SPA container anchor harvest |
| **Workday** (`myworkdayjobs.com`) | Standard job URL pattern matching |
| **Greenhouse** (`job-boards.greenhouse.io`) | Clean link harvesting and description extraction |
| **Lever** (`jobs.lever.co`) | Lever job postings matched |
| **SmartRecruiters** | `smartrecruiters.com` links matched |
| **Taleo** | `taleo.net` links matched |
| **Custom** (Apple, etc.) | `/details/<id>` URL patterns matched |
| **Any other site** | Generic fallback via body text polling + `[DIAG]` self-diagnosis |

---

## Known Site-Specific Behavior

All verified per-company quirks are stored in **`company_urls.csv`** — columns: `company`, `url`, `ats_type`, `notes`.

> **Note**: URLs are only cached in `company_urls.csv` *after* a successful scrape verifies them end-to-end.

| Company | ATS Type | Quick Notes |
|---------|----------|-------------|
| **Amazon** | Custom | Custom `amazon.jobs` portal; `/en/jobs/<ID>/<slug>` links; numeric pagination |
| **American Express** | Eightfold | Shadow DOM cards; Cookie reject; SPA wait; "Show More Results" pagination |
| **United Airlines** | Phenom | JS SPA — networkidle wait required; experience in body text |
| **ZS Careers** | Phenom | Standard, reliable; no login wall |
| **EXL Service** | Oracle HCM | Tenant subdomain not guessable; SmartRecruiters false positive risk |
| **Apple** | Custom | Job URLs: `/details/<ID>/<slug>`; filter `/locationPicker` links |

---

## CLI Reference (Manual Usage)

You can also run every tool directly from the terminal:

### 1. Resolve Company URL (`find_url.py`)
```bash
python find_url.py --company "Amazon" --location "India"
```
- Checks `company_urls.csv` cache first (`CACHE ⚡`).
- If not cached, pings 17 candidate ATS URLs in parallel and returns ranked confidence (`HIGH ✅`, `MEDIUM ⚠️`, `LOW 🔸`, `DEAD ❌`).

### 2. Scrape Job Listings (`scraper.py`)
```bash
python scraper.py --url "<target-careers-url>" --company "<company-name>" --output jobs_raw.json
```
- `--url`: Target careers/search URL with location filters applied.
- `--company`: Company name used for file naming and logging.
- `--output`: Path to output JSON (default: `jobs_raw.json`).

### 3. Analyze & Rank Jobs (`analyze.py`)
```bash
python analyze.py --input jobs_raw.json --max-yoe 2
```
- `--input`: Path to input scraped jobs JSON (default: `jobs_raw.json`).
- `--max-yoe`: Maximum years of experience threshold to classify as "Good/Strong" match (default: `2`).
- `--no-md`: Skip generating the `data/analysis_<date>.md` file on disk (outputs to console only).

### 4. Windows Visible Console Launcher (`launch.py`)
```bash
python launch.py --url "<target-careers-url>" --company "<company-name>"
```
- Spawns scraper in a separate visible Windows console window while tailing the log in real time.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No jobs found | `[DIAG]` dump fires automatically — reads raw anchors and suggests selector / URL fixes |
| Shadow DOM cards (e.g. Eightfold) | Playwright locators automatically pierce shadow DOM as fallback |
| Jobs rendered as divs, not links | `[DIAG]` non-anchor dump identifies the element for custom extraction |
| Jobs blocked (403 on descriptions) | Script falls back to partial text — still saves what it gets |
| CAPTCHA | Solve it in the browser window — script polls every 3s and auto-resumes once cleared |
| Cookie dialog blocking page | Script auto-dismisses (Reject All first, Accept as fallback) |
| Page looks empty (SPA not hydrated) | Script waits up to 12s for job card elements before harvesting |
| `playwright` not found | Run `playwright install chromium` |
| Browser doesn't appear | Run `launch.py` directly to force a visible Windows console |

---

## Default Behavior (AI-Controlled Mode)

| Setting | Default |
|---------|---------|
| Location | **India** (Gurgaon, Pune, Bengaluru, Hyderabad, Noida, Chennai, Mumbai) |
| Experience target | **Fresher / 0–2 years** |
| Parallel tabs | 5 simultaneous Playwright tabs |
| Max pages | 30 (safety cap) |
| Description cap | 8000 chars per job |

