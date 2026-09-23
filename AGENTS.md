# Agent Rules — AI Job Scraper Workspace

This workspace contains a chat-controlled job scraper. The user never touches the terminal or sets filters manually. The agent does everything.

---

## Trigger Rule — When to Run the Scraper

Any message from the user that sounds like a casual job search request **always means: run scraper.py immediately**. Do not browse the web, do not use read_url, do not use a browser subagent to inspect the site first.

Examples of trigger phrases:
- "check X jobs for me"
- "can you look at X careers"
- "search X for fresher roles"
- "what does X have open"
- "any jobs at X?"

**Action**: Construct the best filtered URL you can, run `scraper.py` as a background task, and let the headed browser handle the rest. The user can adjust filters visually in the browser if needed.

---

## My Role

- User tells me a company, role criteria, and preferences **in chat**
- I run `scraper.py` on their behalf
- I monitor output for CAPTCHA or errors and relay to user
- I read `jobs_raw.json` and report a match table in chat
- User stays in the chat the entire time

---

## How to Run a Scrape

```powershell
cd C:\Users\stark\Desktop\Utility\jobs
python scraper.py --url "<filtered_career_url>" --output jobs_raw.json
```

Run as a background task (`IsDaemon=false`, `WaitMsBeforeAsync=5000`).

### Constructing the URL & Defaults
- **Default Location**: Always default to **India** (Gurgaon, Pune, Bengaluru, Hyderabad, Noida, Chennai, etc.) unless the user explicitly specifies another country.
- **Default Experience Level**: Target **Fresher / 0 years experience** (0-2 years entry-level).
- Embed filters directly in the URL where possible (e.g., `?location=India&...`).
- For ZS Careers, use: `https://jobs.zs.com/all/jobs?location=India&woe=12&regionCode=IN`
- For United Airlines (Phenom/Workday), use filtered India careers page URL.
- For other companies, inspect the URL after applying filters.

---

## Monitoring the Script Output

Watch the task log file continuously. Key signals to look for:

| Signal in Output | What to Do |
|-----------------|------------|
| `CAPTCHA_DETECTED` | **Immediately tell user in chat**: "🛑 CAPTCHA detected — please solve it in the browser window on your screen. The script will resume automatically." |
| `NO_JOBS_FOUND` | Tell user no results — suggest adjusting filters or URL |
| `SCRAPE_COMPLETE` | Read `jobs_raw.json` and proceed to analysis |
| `HTTP 403` on many jobs | Background fetching is blocked — consider Playwright fallback |

---

## Analyzing Results

After `SCRAPE_COMPLETE`, read `jobs_raw.json`:

```powershell
Get-Content C:\Users\stark\Desktop\Utility\jobs\jobs_raw.json
```

Then apply the user's criteria to each job's `description` field. Look for:
- **Years of experience** required (fresher = 0 years / 0–2 years, or "fresh graduate", "entry level")
- **Date posted** (if mentioned in page text e.g., "Posted 3 days ago", "Date: 2026-09-15")
- **Role match** (match against what the user asked for)
- **Location match** (India cities unless specified otherwise)

### Output Format (always use this table in chat)

| # | Job Title | Location | Experience | Posted Date | Match | Apply |
|---|-----------|----------|------------|-------------|-------|-------|
| 1 | Decision Analytics Associate | Pune | 0–2 yrs | 3 days ago | ⭐⭐⭐ Strong | [Apply](url) |
| 2 | Business Technology Associate | Gurgaon | Fresh grad | Recent | ⭐⭐ Good | [Apply](url) |

- ⭐⭐⭐ **Strong** — Meets all criteria (0 yrs / fresher friendly)
- ⭐⭐ **Good** — Meets most criteria, minor gaps
- ⭐ **Weak** — Only partially relevant, mention why

Always include the direct job URL as the Apply link.

> **CRITICAL: Never infer experience from job title.**
> Always extract the exact experience string from `description` text.
> Look for patterns like:
> - `"Experience: 1+ year"` (UAL Phenom ATS format)
> - `"at least 6 months - 2 year experience"`
> - `"0-2 years"`, `"2+ years"`, `"entry level"`, `"fresh graduate"`
> - If no pattern is found, label as **Unknown** — do NOT guess.
> Run `analyze.py` (see Files section) to extract this automatically.

---

## Workflow Summary

```
User: "Search <company>, <location>, <role/criteria>"
  ↓
Agent: Constructs filtered URL
  ↓
Agent: Runs scraper.py (background task)
  ↓
Script: Opens headed browser, navigates, auto-detects CAPTCHA
  ↓
[If CAPTCHA] → Agent tells user → User solves → Script auto-resumes
  ↓
Script: Sweeps all pages, parallel-fetches all job descriptions
  ↓
Script: Saves jobs_raw.json, prints SCRAPE_COMPLETE
  ↓
Agent: Reads file, matches against criteria, posts result table in chat
```

---

## Files in This Workspace

| File | Purpose |
|------|---------|
| `scraper.py` | Main scraper — Playwright + async parallel fetch |
| `analyze.py` | Post-scrape analyzer — extracts exact YOE from description text, outputs ranked table + markdown |
| `requirements.txt` | `playwright`, `aiohttp` |
| `jobs_raw.json` | Output from latest scrape run |
| `README.md` | User-facing guide |
| `AGENTS.md` | This file — agent instructions |

---

## Known Behaviors

- The script polls every 3 seconds to detect CAPTCHA resolution — no user terminal input needed
- Session cookies from the headed browser are reused for background fetching (reduces 403s)
- Link extraction is DOM-agnostic — uses JS to harvest all `<a href>` tags that match job URL patterns
- Descriptions are capped at 8000 chars per job to stay within context limits

---

## Site-Specific Scraping Notes

### United Airlines (careers.united.com — Phenom ATS)
- Job pages are a **fully JS-rendered SPA** — `domcontentloaded` fires before content loads
- Must use `wait_until="networkidle"` + poll `body.innerText.length > 1500` before extracting
- CAPTCHA may appear during description fetch; do **not** block on it — log and skip, data is still saved
- Experience is often written as `"Experience: 1+ year"` in the job body (not in a structured field)
- **"Associate" in title does NOT mean entry-level** — always read the description
- Save happens immediately after all fetches complete, before browser teardown

### ZS Careers (jobs.zs.com)
- Standard Phenom ATS, loads reliably with networkidle
- No login wall on job detail pages
- Use URL: `https://jobs.zs.com/all/jobs?location=India&woe=12&regionCode=IN`

### EXL Service (jobs.exlservice.com)
- Uses Eightfold AI ATS
- Career portal: `https://jobs.exlservice.com/`
- For India/Gurugram/Noida, use: `https://jobs.exlservice.com/?location=Gurugram%2C+Haryana%2C+India&location=Noida%2C+Uttar+Pradesh%2C+India`
- Job URLs follow pattern: `https://jobs.exlservice.com/jobs/<id>`
- Eightfold renders via JS — use networkidle + body text polling fallback
