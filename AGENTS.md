# Agent Rules — AI Job Scraper Workspace

This workspace contains a chat-controlled job scraper. The user never touches the terminal or sets filters manually. The agent does everything.

---

## Trigger Rule — When to Run the Scraper

Any message from the user that sounds like a casual job search request **always means: run scraper.py immediately**. Do not browse the web, do not use read_url, **do not use a browser subagent to inspect the site first** (slow — only as last resort after 2 failed fix attempts).

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

### Step 0 (always): Resolve the correct URL first

Before running `scraper.py`, run `find_url.py` to identify the correct ATS URL:

```powershell
python find_url.py --company "EXL Service" --location "Gurugram"
```

This checks `company_urls.csv` cache first. If not found, it pings candidate ATS URLs in parallel and returns a ranked confidence table:
- **CACHE** (⚡) — Found in `company_urls.csv`. Fast & verified.
- **HIGH** (✅) — 200 OK + body confirms careers page. Use this URL.
- **MEDIUM** (⚠️) — 200 OK but couldn't fully confirm. Try in scraper, user can adjust.
- **LOW** (🔸) — Redirected to wrong domain or suspicious.
- **DEAD** (❌) — 404 or connection error.

Pick the **best HIGH or MEDIUM** URL, and pass it to `scraper.py`.

> **CRITICAL URL CACHE RULE**:
> Only add or update a company entry in `company_urls.csv` **AFTER a successful scrape (`SCRAPE_COMPLETE`)** has verified that the URL works end-to-end. Never add or update URLs speculatively before scraping.

If **NO_URL_FOUND** or all results are DEAD/LOW: **ask the user in chat**:
> "I couldn't find the careers page URL for [company] automatically. Could you paste the link to their jobs page? (e.g. the URL you see when you're on their careers/jobs listing)"

No shame — Oracle HCM, custom ATS tenants, and internal portals are not guessable. The user knows the URL. Once they paste it, run `scraper.py` immediately with that URL.

### Step 1: Run the scraper

```powershell
python scraper.py --url "<url-from-find_url>" --company "EXL" --output jobs_raw.json
```

Run as a background task (`IsDaemon=false`, `WaitMsBeforeAsync=5000`).

### URL Defaults
- **Default Location**: Always default to **India** (Gurgaon, Pune, Bengaluru, Hyderabad, Noida, Chennai, etc.) unless the user explicitly specifies another country.
- **Default Experience Level**: Target **Fresher / 0 years experience** (0-2 years entry-level).
- Embed filters directly in the URL where possible (e.g., `?location=India&...`).
- For known companies, `find_url.py` resolves the correct URL from `company_urls.csv` automatically.

---

## Monitoring the Script Output

**MANDATORY: Always set a 90-second auto-monitor timer immediately after launching scraper.py.**

```
After run_command(scraper.py ..., IsDaemon=false, WaitMsBeforeAsync=5000):
  → set schedule(DurationSeconds=90, TimerCondition=<task-id>,
      Prompt="Check task-<id> status. If SCRAPE_COMPLETE, read jobs_raw.json
              and run analyze.py. If still running, report progress and set
              another 90s timer.")
```

Never make the user ask "?" or "what's happening?" — the timer ensures you always report back proactively.

Watch the task log file continuously. Key signals to look for:

| Signal in Output | What to Do |
|-----------------|------------|
| `CAPTCHA_DETECTED` | **Immediately tell user in chat**: "🛑 CAPTCHA detected — please solve it in the browser window on your screen. The script will resume automatically." |
| `Cookie dialog dismissed (Rejected All)` | ✅ Normal — cookie dialog was auto-dismissed. No action needed. |
| `Cookie dialog dismissed (Accepted — no reject option found)` | ✅ Normal fallback — site had no Reject option. No action needed. |
| `Job cards detected via '...'` | ✅ SPA hydrated — jobs found in DOM before harvest. Good sign. |
| `[WARN] No job card selector matched` | ⚠️ SPA may not have rendered — harvest proceeds anyway. Watch for 0 links. |
| `[DIAG] 0 job links matched` | 🔍 **Read the dump**. Fix `is_job_link()` or URL pattern. Re-run. No browser subagent needed. |
| `Non-anchor job-like elements found` | Jobs rendered as `<div>` not `<a>` — scraper needs a custom extractor for this ATS. |
| `NO_JOBS_FOUND` | After DIAG steps exhausted — tell user, suggest adjusting URL or ask for the correct URL. |
| `SCRAPE_COMPLETE` | Read `jobs_raw.json` and proceed to analysis. |
| `HTTP 403` on many jobs | Background fetching is blocked — consider Playwright fallback. |


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
> Run `python analyze.py --input jobs_raw.json` (Note: use `--input`, NOT `--file`) to extract this automatically.

---

## Workflow Summary

```
User: "Search <company>, <location>, <role/criteria>"
  ↓
Agent: find_url.py → resolve ATS URL (cache first, then ping)
  ↓
Agent: scraper.py → headed browser opens
  ↓
Script: Rejects all cookies automatically (Accepts if no reject option)
  ↓
Script: Waits for job cards to hydrate in DOM (SPA-safe)
  ↓
[If CAPTCHA] → Agent tells user → User solves → Script auto-resumes
  ↓
Script: Sweeps all pages (Next / Load More / Show More Results)
  ↓
[If 0 links] → [DIAG] dump fires → Agent reads, fixes is_job_link() → re-run
              → If still 0 after 2 fixes → ask user for correct URL
              → Browser subagent ONLY if URL is confirmed correct but page still broken
  ↓
Script: Parallel-fetches all job descriptions (5 tabs)
  ↓
Script: Saves jobs_raw.json → SCRAPE_COMPLETE
  ↓
Agent: Reads file, matches criteria, posts table in chat
```

---

## Files in This Workspace

| File | Purpose |
|------|---------|
| `find_url.py` | Pre-scrape URL resolver — checks `company_urls.csv` cache & pings ATS URLs |
| `company_urls.csv` | URL cache — stores pre-verified ATS careers URLs for fast lookup |
| `scraper.py` | Main scraper — Playwright + async parallel fetch |
| `analyze.py` | Post-scrape analyzer — extracts exact YOE from description text, outputs ranked table + markdown |
| `launch.py` | Windows launcher — spawns scraper in visible console, tails log |
| `requirements.txt` | `playwright`, `aiohttp` |
| `jobs_raw.json` | Output from latest scrape run |
| `agent_helper.py` | Agent sandbox — ad-hoc scripts & custom data analysis (pre-approved runner) |
| `README.md` | User-facing guide |
| `AGENTS.md` | This file — agent instructions |

---

## Known Behaviors

- **Cookie handling**: Always tries Reject All first; falls back to Accept only if no reject option exists
- **SPA hydration wait**: After cookie dismiss, polls up to 12s for job card selectors before harvesting — prevents empty harvests on Eightfold, Phenom, Workday
- **Self-diagnosing**: When 0 links found, `[DIAG]` auto-dumps all raw `<a>` hrefs + non-anchor job elements so the agent can fix `is_job_link()` without a browser subagent
- **Pagination**: Handles Next, Load More, Show More Results, numbered pages
- The script polls every 3 seconds to detect CAPTCHA resolution — no user terminal input needed
- Session cookies from the headed browser are reused for background fetching (reduces 403s)
- Link extraction is DOM-agnostic — uses JS to harvest all `<a href>` tags that match job URL patterns
- Descriptions are capped at 8000 chars per job to stay within context limits

## Failure Escalation Policy (0 jobs found)

```
1. Read [DIAG] dump → fix is_job_link() or URL → re-run          (fast, ~1 min)
2. Try without location filter → confirm jobs exist at all         (fast, ~1 min)
3. Ask user to paste the correct careers URL                       (instant)
4. Browser subagent inspection                                     (slow, last resort only)
```

Never jump to step 4 before exhausting steps 1–3.

---

## Site-Specific Scraping Notes

All per-company scraping quirks (ATS type, URL, known gotchas) are stored in **`company_urls.csv`** — the `notes` column is the single source of truth.

When encountering a known company, always read the `notes` field from the CSV row before scraping. Key things to look for:
- ATS rendering behavior (SPA vs SSR, selector waits needed)
- Experience string format in job descriptions
- Links to filter out (noise links, location pickers)
- Known false positives or redirect traps

To add a new company's quirks: update `company_urls.csv` with `ats_type` and `notes` **only after a successful scrape run**. Do not add unverified URLs beforehand. Do not add site-specific notes back into this file.

---

## One-Off & Ad-Hoc Scripts Rule (`agent_helper.py`)

- **Never propose inline `python -c "..."` commands**: Inline shell commands trigger repetitive approval prompts.
- **Always write one-off / ad-hoc analysis or diagnostic code into `agent_helper.py`**:
  Update `agent_helper.py` using file editing tools, and execute it via `python agent_helper.py`. This ensures a single consistent command that can be run smoothly without repeated approvals.

