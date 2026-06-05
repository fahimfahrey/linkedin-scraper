# LinkedIn Scraper: Automated Lead Collection with Anti-Ban Guardrails

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architectural Design](#architectural-design)
3. [Prerequisites & System Requirements](#prerequisites--system-requirements)
4. [Step-by-Step Installation](#step-by-step-installation)
5. [Authentication & Session Initialization](#authentication--session-initialization)
6. [Operational Guide: Bulk Scraping](#operational-guide-bulk-scraping)
7. [SQLite Database Schema](#sqlite-database-schema)
8. [Data Export & Reporting](#data-export--reporting)
9. [Anti-Ban Safety & Execution Thresholds](#anti-ban-safety--execution-thresholds)
10. [Troubleshooting & Recovery](#troubleshooting--recovery)
11. [Testing & Validation](#testing--validation)
12. [Environment Variables & Configuration](#environment-variables--configuration)
13. [Legal & Security Notices](#legal--security-notices)
14. [Project Structure & Key Files](#project-structure--key-files)

---

## Project Overview

**One-sentence summary:** Automated LinkedIn profile scraper with anti-ban guardrails, MFA authentication, and Streamlit dashboard for bulk lead generation with rate limiting.

This project provides an end-to-end solution for collecting LinkedIn profile data at scale while respecting platform security constraints. It combines:

- **Playwright** for headless Chromium automation with stealth evasion techniques
- **Streamlit** for real-time dashboard UI with session state management
- **SQLite** for persistent profile storage with automatic deduplication

The scraper enforces a **conservative 45 profiles/day limit** to avoid 24-hour bans, monitors for security incidents (CAPTCHA, forced logout, rate limits), and provides detailed logging and recovery procedures for operational teams.

**Primary use cases:**
- B2B lead generation with compliance-first design
- Bulk profile collection for CRM enrichment
- Research and market analysis with transparent throttling

**Key features:**
- Session persistence with MFA support (cookies + localStorage + sessionStorage)
- Humanized request delays (2–5s random between requests, 1–3s scroll delays)
- Real-time UI monitoring: profiles collected, anomalies detected, execution window status
- Bulk URL import via copy-paste (one per line)
- CSV and Excel export with formatted headers
- Graceful shutdown with queue-based thread communication

---

## Architectural Design

### System Stack: Playwright + Streamlit + SQLite

```
┌─────────────────────────────────────────────────────────┐
│                  Streamlit UI Layer                      │
│  (Session state, thread spawning, real-time messaging)  │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│           Threading Layer (Queue-Based IPC)              │
│  (ScraperWorker manages background thread lifecycle)    │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│        Playwright + Stealth Layer (Headless Chromium)   │
│  (Profile scraping, delay injection, anomaly detection) │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│           Anti-Ban Guardrails (ExecutionWindow)          │
│  (Daily limit enforcement, anomaly detection, logging)  │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│         SQLite + Deduplication (linkedin_profiles)       │
│  (UNIQUE constraint on linkedin_url, INSERT OR IGNORE)  │
└─────────────────────────────────────────────────────────┘
```

### Layer Details

#### Playwright Layer
- **Headless Chromium** for browser automation
- **playwright-stealth** plugin masks automation markers (hides `navigator.webdriver`)
- **Async/await** for non-blocking I/O with proper resource cleanup
- **Custom environment mapping** for Linux Chromium runtime (DISPLAY, LD_LIBRARY_PATH, HOME, TMPDIR)

#### Streamlit Layer
- **Session state** (`st.session_state`) persists authentication, thread references, and status log across reruns
- **Thread spawning** (non-blocking) via `ScraperWorker.spawn(urls, env, window_controller, anomaly_detector)`
- **Message consumption** (0.1s polling interval) pulls StatusUpdate, ProfilePayload, OperationWarning from queue
- **Real-time UI** shows collected profiles, status log, daily limit counter, anomalies in live view

#### Threading Model
- **Main thread:** Streamlit reruns (~0.5s polling), pulls messages from queue, updates UI state
- **Worker thread:** Asyncio event loop runs `scrape_profile_batch()`, publishes messages (non-blocking put)
- **Queue communication:** `queue.Queue(maxsize=1000)` decouples scraper lifecycle from UI reruns
- **Graceful shutdown:** `_stop_event` (threading.Event) signals worker to stop; UI waits 30s for drain

#### SQLite Layer
- **Schema:** Single table `linkedin_profiles` with UNIQUE constraint on `linkedin_url`
- **Deduplication:** `INSERT OR IGNORE` semantics; duplicate URL attempts return 0 rows, logged as "Duplicate ignored"
- **Persistence:** Append-only; no DELETE operations (data integrity)
- **Access:** `database.py` functions (`get_profiles_df`, `insert_profile`) handle all SQL

---

## Prerequisites & System Requirements

- **Python 3.8+** (tested on 3.10, 3.14; 3.8 minimum for async/await support)
- **Ubuntu 26.04 or Debian-based Linux** (CentOS/RHEL may require additional Xvfb and library setup)
- **4GB RAM minimum** (Chromium runs 300–500MB; Python/Streamlit ~200MB; headroom for OS/cache)
- **Xvfb or DISPLAY** for headless environments (virtual display server)
- **Network stability** (outbound HTTPS to `linkedin.com`; no proxies required, but supported via Playwright)
- **Disk space:** ~500MB for Playwright browsers, 100MB per 10K profiles in SQLite

### Ubuntu 26.04 Special Considerations

Ubuntu 26.04 uses glibc 2.39+ and newer system libraries. **Critical issue:** Playwright's auto-detection on Ubuntu 26.04 may select `ubuntu22.04-x64` or `ubuntu20.04-x64` drivers, causing `GLIBC_2.38 not found` or Chromium segfaults. This is resolved by **explicit platform override** (see [Installation](#step-by-step-installation)).

---

## Step-by-Step Installation

> **Quick tip:** For detailed installation instructions, dependency troubleshooting, or Docker setup, see [INSTALL.md](INSTALL.md) and [docs/PLAYWRIGHT_SETUP.md](docs/PLAYWRIGHT_SETUP.md).

### 1. Clone Repository

```bash
git clone https://github.com/yourorg/linkedin-scraper.git
cd linkedin-scraper
```

### 2. Create Python Virtual Environment

```bash
python -m venv venv
source venv/bin/activate
```

### 3. **[CRITICAL] Set PLAYWRIGHT_HOST_PLATFORM_OVERRIDE for Ubuntu 24.04+**

⚠️ **This step is essential on Ubuntu 24.04 and later. Skipping it will cause browser driver mismatches.**

Playwright auto-detects the platform and downloads matching browser binaries. On newer Ubuntu versions, auto-detection may fail, causing compatibility issues. Explicitly override:

```bash
export PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64
```

Add to your shell profile for persistence:

```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'export PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64' >> ~/.bashrc
source ~/.bashrc
```

Or add to `.env` file (see [Environment Variables](#environment-variables--configuration)).

### 4. Install System Dependencies (Ubuntu/Debian)

For Ubuntu 24.04 or later, run the automated setup script:

```bash
./scripts/setup-playwright-deps.sh
```

For other systems, see [docs/PLAYWRIGHT_SETUP.md](docs/PLAYWRIGHT_SETUP.md#troubleshooting) for manual installation instructions.

### 5. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Key packages:**
- `playwright` — headless browser automation
- `playwright-stealth` — masks automation detection
- `streamlit` — UI framework
- `pandas` — data manipulation and export
- `beautifulsoup4` — HTML parsing (fallback if needed)
- `pytest` / `pytest-asyncio` — testing framework
- `openpyxl` — Excel export (optional but recommended)

### 6. Install Playwright Browsers

```bash
python -m playwright install
```

This downloads Chromium, Firefox, and WebKit browsers (only Chromium needed; others optional).

**Troubleshooting:** If you see warnings about missing system dependencies, run:
```bash
python -m playwright install --with-deps
```

See [docs/PLAYWRIGHT_SETUP.md](docs/PLAYWRIGHT_SETUP.md) for detailed troubleshooting.

### 7. Configure Credentials

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your LinkedIn account (for headless login; interactive login is preferred for MFA):

```bash
# .env file
LINKEDIN_EMAIL=your-email@example.com
LINKEDIN_PASSWORD=your-password  # Only needed if MFA not required
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64
DEBUG=False
LOG_LEVEL=INFO
```

**Security reminder:** `.env` is in `.gitignore` and should never be committed.

### 8. Initialize Database

```bash
python -c "from database import init_db; init_db()"
```

Or run the self-test:

```bash
python database.py
```

Expected output:
```
DB initialised at linkedin_profiles.db
All assertions passed. DB layer functional.
  id  linkedin_url          full_name  headline  ...
   1  https://www.linked... Test User Software Engineer  ...
```

### 9. Start Streamlit Application

```bash
streamlit run app.py
```

**Expected output:**
```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

Open browser to `http://localhost:8501`.

---

## Authentication & Session Initialization

LinkedIn uses session-based authentication (cookies + localStorage + sessionStorage). The scraper stores these in `session.json` (Playwright's native storage format) and reuses them across restarts.

### Session Format

`session.json` is a JSON file with structure:

```json
{
  "cookies": [
    {
      "name": "li_at",
      "value": "AQFFb...",
      "domain": "linkedin.com",
      "path": "/",
      "expires": 1720000000,
      "httpOnly": true,
      "secure": true,
      "sameSite": "None"
    }
  ],
  "origins": [
    {
      "origin": "https://www.linkedin.com",
      "localStorage": [
        {"name": "key", "value": "..."}
      ],
      "sessionStorage": []
    }
  ]
}
```

**Critical cookies:**
- `li_at` — authentication token (expires ~24h)
- `li_netsessionid` — session identifier
- `JSESSIONID` — Java session token

### Interactive Login Flow

1. **Click "Launch Interactive Login"** button in Streamlit sidebar
2. **Browser opens** (non-headless) to LinkedIn login page
3. **Enter email/password** and complete 2FA (SMS, authenticator app, or email code)
4. **Automatic detection:** App monitors for navigation to `/feed/**` (authenticated state)
5. **Session saved:** `session.json` created with all cookies and storage
6. **Status updated:** UI shows ✅ "Auth successful!"

**MFA timeout:** Default 120 seconds (2 minutes). Increase if needed:

```python
# In app.py, modify:
manager = SessionManager(SESSION_FILE, mfa_timeout=300000)  # 5 minutes
```

### Session Revalidation

To refresh or validate an existing session:

1. Click **"Revalidate Session"** button (if available in sidebar)
2. App checks `li_at` cookie expiry and profile accessibility
3. If valid: ✅ "Session valid until YYYY-MM-DD HH:MM:SS"
4. If expired: ❌ "Session expired. Re-authenticate."

### Troubleshooting Authentication

**Issue: "Session expired / 401 Unauthorized"**
- Solution: Click "Launch Interactive Login" to re-authenticate. Session tokens expire ~24h.

**Issue: "MFA timeout / manually completed login"**
- Increase `mfa_timeout` parameter (see above).
- If timeout still insufficient, check browser for stuck login form; click "Revalidate Session" after completing 2FA manually.

**Issue: "session.json missing / corrupted"**
- Delete `session.json`: `rm session.json`
- Click "Launch Interactive Login" to create fresh session.

---

## Operational Guide: Bulk Scraping

### Loading Profile URLs

The scraper accepts a list of LinkedIn profile URLs. Format supported:

```
https://www.linkedin.com/in/username
https://linkedin.com/in/username/
https://www.linkedin.com/in/username-123
https://www.linkedin.com/in/jane-smith-456/
```

**Input method:** Copy-paste into sidebar text area labeled "📋 Paste URLs (one per line or comma-separated)".

Example input:
```
https://www.linkedin.com/in/john-doe
https://www.linkedin.com/in/jane-smith/
https://www.linkedin.com/in/bob-wilson
```

**Invalid formats** (auto-logged, URL skipped):
- Company pages: `https://www.linkedin.com/company/acme/` (detected, logged as "Non-profile URL, skipping")
- Malformed URLs: `linkedin/john` (invalid format)
- Empty lines (ignored)

### Launching Scrape

1. **Load URLs** into sidebar text area
2. Click **"Start Collection"** button
3. **Real-time monitoring:**
   - Status log updates every 0.1s with format: `[SUCCESS] https://linkedin.com/in/... (3.2s)`
   - Counter shows: `Progress: 5/100 profiles (8 min elapsed)`
   - Daily limit tracker: `Daily limit: 12/45 profiles`

### Monitoring During Scrape

**Status log shows:**
- `[SUCCESS]` — Profile collected and inserted into DB
- `[DUPLICATE]` — URL already in DB; insert ignored
- `[ERROR]` — Network error, 404, or parsing failure
- `[ANOMALY]` — Security incident (rate limit, CAPTCHA, redirect); scraper paused

**Anomaly warnings appear as:**
```
ANOMALY: rate_limit detected. Status: 429. URL: https://...
(Scraper paused. Resume after 2–4 hours.)
```

### Stopping Gracefully

Click **"Stop Collection"** button. App:
1. Sets stop event (signals worker to halt)
2. Waits up to 30 seconds for current request to complete
3. Drains remaining messages from queue
4. Updates UI with final count and elapsed time

**Note:** Already-queued URLs are **not processed** after stop. Partial results are saved to DB.

### Handling Rate Limits (429)

**Symptom:** Status log shows `[ANOMALY] rate_limit detected. Status: 429`

**Root cause:** LinkedIn detected suspicious pattern (too many requests in short time).

**Recovery steps:**
1. Click "Stop Collection"
2. **Wait 2–4 hours** (conservative; LinkedIn may lift block faster)
3. Check daily counter — if you hit 45, wait until **midnight UTC** for automatic reset
4. Resume by clicking "Start Collection" again with remaining URLs

**Tuning:** To reduce future rate limits, increase random delays in `scraper.py`:

```python
# In scraper.py, find:
delay = random.uniform(2, 5)  # Default: 2–5 seconds

# Change to:
delay = random.uniform(4, 8)  # More conservative: 4–8 seconds
```

---

## SQLite Database Schema

### Table: `linkedin_profiles`

```sql
CREATE TABLE IF NOT EXISTS linkedin_profiles (
    id              INTEGER PRIMARY KEY,
    linkedin_url    TEXT UNIQUE,
    full_name       TEXT,
    headline        TEXT,
    location        TEXT,
    current_company TEXT,
    about_text      TEXT,
    experience_json TEXT,
    education_json  TEXT,
    collected_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Column Definitions

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY | Auto-increment, unique identifier |
| `linkedin_url` | TEXT UNIQUE | Deduplication key; insertion with duplicate URL silently ignored |
| `full_name` | TEXT | Extracted from profile header; may be NULL if not found |
| `headline` | TEXT | Job title + company (e.g., "Senior SWE @ Google") |
| `location` | TEXT | City + region (e.g., "San Francisco, CA") |
| `current_company` | TEXT | Employer name; may change if unemployed |
| `about_text` | TEXT | Bio/summary section (may be long; CLOB in SQLite terms) |
| `experience_json` | TEXT | JSON array: `[{"title": "...", "company": "...", "dates": "..."}]` |
| `education_json` | TEXT | JSON array: `[{"school": "...", "degree": "...", "field": "..."}]` |
| `collected_at` | TIMESTAMP | Server timestamp when profile was inserted; NOT when collected by scraper |

### Constraints

- **UNIQUE(linkedin_url):** Prevents duplicate inserts. If same URL posted twice, 2nd insert returns 0 rows (logged as "Duplicate ignored").
- **NOT NULL:** Only `id` is implicitly NOT NULL (PRIMARY KEY). All other columns nullable (profiles may be incomplete).

### Example Query: Count Profiles by Company

```sql
SELECT current_company, COUNT(*) as count
FROM linkedin_profiles
WHERE current_company IS NOT NULL
GROUP BY current_company
ORDER BY count DESC
LIMIT 10;
```

### Example Query: Check for Actual Duplicates

If data looks duplicated despite UNIQUE constraint:

```sql
SELECT linkedin_url, COUNT(*) as count
FROM linkedin_profiles
GROUP BY linkedin_url
HAVING COUNT(*) > 1;
```

(Should return 0 rows if constraint is working.)

### Example Query: Export Profiles from Specific Company

```sql
SELECT id, full_name, headline, location
FROM linkedin_profiles
WHERE current_company = 'Google'
ORDER BY collected_at DESC;
```

### Access via Python

```python
from database import get_profiles_df, insert_profile

# Get all profiles as DataFrame
df = get_profiles_df("linkedin_profiles.db")
print(df.head(10))

# Insert single profile
profile = {
    "linkedin_url": "https://www.linkedin.com/in/john-doe",
    "full_name": "John Doe",
    "headline": "Software Engineer @ Acme Corp",
    "location": "San Francisco, CA",
    "current_company": "Acme Corp",
    "about_text": "Builder of things.",
    "experience_json": '{"title": "SWE", "company": "Acme"}',
    "education_json": '{"school": "MIT", "degree": "BS CS"}',
}
inserted = insert_profile(profile)
print(f"Inserted: {inserted}")  # True if new, False if duplicate
```

---

## Data Export & Reporting

### CSV Export

**Use case:** Import to marketing automation (HubSpot, Salesforce), data pipeline, or spreadsheet processing.

**How to export:**
1. In Streamlit app, sidebar widget: **"📥 Download CSV"**
2. Browser downloads `linkedin_profiles_export_20260605_142530.csv`
3. Encoding: UTF-8

**Format:**
```csv
full_name,headline,location,current_company,linkedin_url,about_text,collected_at
John Doe,Senior SWE @ Google,San Francisco CA,Google,https://www.linkedin.com/in/john-doe,Builder of things.,2026-06-05 14:25:30
Jane Smith,Product Manager @ Facebook,Seattle WA,Facebook,https://www.linkedin.com/in/jane-smith,...,2026-06-05 14:26:15
```

### Excel Export

**Use case:** Manual review, pivot tables, VLOOKUPS, team sharing.

**How to export:**
1. In Streamlit app, sidebar widget: **"📥 Download Excel"**
2. Browser downloads `linkedin_profiles_export_20260605_142530.xlsx`

**Features:**
- Frozen header row (scrollable data below)
- Auto-sized columns (width fits content, max 50 chars)
- Sheet name: "Profiles"

### Advanced Queries

**Deduplication check:**
```sql
SELECT linkedin_url, COUNT(*) FROM linkedin_profiles
GROUP BY linkedin_url HAVING COUNT(*) > 1;
```

**Profiles by decade of data collection:**
```sql
SELECT DATE(collected_at) as date, COUNT(*) as count
FROM linkedin_profiles
GROUP BY DATE(collected_at)
ORDER BY date DESC;
```

**Education distribution:**
```sql
SELECT 
  json_extract(education_json, '$[0].school') as school,
  COUNT(*) as count
FROM linkedin_profiles
WHERE education_json IS NOT NULL
GROUP BY school
ORDER BY count DESC
LIMIT 20;
```

---

## Anti-Ban Safety & Execution Thresholds

LinkedIn's security team monitors for bot activity. This scraper enforces conservative limits to stay below detection thresholds.

### Daily Execution Window (45 Profiles/Day)

**Default limit:** 45 profiles collected per day (UTC timezone).

**Rationale:**
- LinkedIn limits legitimate user activity to ~50–100 profile views/day
- Conservative 45-profile cap provides safety margin
- Accounts aged <3 months more aggressive, so 45 is safe baseline
- Hard limit prevents cascading bans (one account doesn't endanger organization)

**How it works:**
1. `ExecutionWindowController` loads state from `execution_window.json`
2. On first run of day, checks `date` field; if today's date, uses stored count; else resets to 0
3. Before each profile scrape, calls `check_and_increment()`:
   - If count >= 45, raises `ExecutionWindowExceeded` exception
   - Scraper logs warning and stops
   - UI shows "Daily limit reached: 45/45"

**Example state file:**
```json
{
  "date": "2026-06-05",
  "count": 23,
  "reset_count": 5
}
```

**Tuning (if needed):**
- Edit `scraper.py`, line 55: `max_profiles_per_day: int = 45`
- Change to higher value (e.g., 100) only after 2+ weeks of successful runs on account
- Risk increases exponentially above 50/day; not recommended

### Humanized Request Delays

LinkedIn detects bots by analyzing request patterns:
- **Fixed delays:** "request every 3 seconds" → bot pattern
- **Random delays:** "request every 2–5 seconds (random)" → human-like

**Implemented delays:**
- **Between requests:** `random.uniform(2, 5)` seconds (default)
- **Scroll action:** `random.uniform(1, 3)` seconds (simulates reading)
- **Click action:** `random.uniform(0.5, 1.5)` seconds
- **Page load wait:** Max 10 seconds (Playwright timeout)

**Configuration:**
In `scraper.py`, search for `random.uniform()` calls and adjust ranges:

```python
# Default (conservative)
delay = random.uniform(2, 5)

# More aggressive (higher risk)
delay = random.uniform(1, 3)

# Very conservative (slow)
delay = random.uniform(5, 10)
```

### Stealth Plugin & Chromium Configuration

**Stealth techniques:**
1. **playwright-stealth plugin** — masks `navigator.webdriver` (primary bot detection vector)
2. **Headless mode disabled** (during interactive auth) — renders with GPU for pixel-perfect rendering
3. **User-Agent:** Default Chromium user agent (no modification; realistic)
4. **WebGL/canvas fingerprinting:** Not spoofed (harder to detect, less critical)

**Environment configuration:**
In `environment_config.py`:
- `DISPLAY=:99` — Xvfb virtual display (Linux headless rendering)
- `LD_LIBRARY_PATH` — Runtime libraries for Chromium (glibc, X11)
- `HOME` — User home for Chromium cache (`~/.cache/ms-playwright`)
- `TMPDIR=/tmp` — Temp directory for Chromium temp files

**Code example (scraper.py):**
```python
from playwright_stealth import Stealth

context = await browser.new_context()
Stealth.enable(context)  # Applies all stealth patches
page = await context.new_page()
```

### Anomaly Detection

`AnomalyDetector` inspects HTTP responses and page content for security incidents:

| Anomaly Type | Detection | Action |
|--------------|-----------|--------|
| **captcha** | Regex match on `recaptcha`, `hcaptcha`, `challenge` in page content | Log critical, raise `SecurityIncidentDetected`, stop scraper |
| **forced_logout** | Page title matches `sign.?in` or URL is `/`, OR `li_at` cookie expired | Log critical, raise exception, stop scraper |
| **rate_limit** | HTTP 429 response, OR page text matches `too.?many`, `slow.?down` | Log warning, emit `OperationWarning` to UI, pause 5m |
| **redirect_anomaly** | URL changed mid-scrape (e.g., to `/errors/` page) | Log warning, skip this URL, continue |

**Example log output:**
```
SECURITY INCIDENT: CAPTCHA detected. Emergency shutdown initiated.
ANOMALY: rate_limit detected. Details: HTTP 429, https://linkedin.com/in/...
```

---

## Troubleshooting & Recovery

### Issue: "Playwright browser not found"

**Error message:**
```
PlaywrightError: Executable doesn't exist at /path/to/chromium
```

**Root causes:**
1. Playwright not installed: `pip install playwright` not run
2. Browsers not downloaded: `python -m playwright install` not run
3. Wrong platform override: PLAYWRIGHT_HOST_PLATFORM_OVERRIDE set incorrectly

**Solutions:**
1. Run: `python -m playwright install`
2. Verify override (if on Ubuntu 26.04): `export PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64`
3. Check path: `ls ~/.cache/ms-playwright/chromium-*/chrome`
4. If not found, re-run with override and clean cache: `rm -rf ~/.cache/ms-playwright && python -m playwright install`

---

### Issue: "Session expired / 401 Unauthorized"

**Error message:**
```
AnomalyDetector: Forced logout detected. li_at cookie expired or invalid.
```

**Root cause:** LinkedIn session tokens expire every 12–24 hours.

**Solution:**
1. Click "Launch Interactive Login" to re-authenticate
2. Complete 2FA if prompted
3. `session.json` will be overwritten with fresh session
4. Resume scraping

---

### Issue: "Daily limit reached (45/45)"

**Error message:**
```
ExecutionWindowExceeded: Daily profile limit (45) exceeded
```

**Root cause:** 45 profiles collected today (UTC timezone); hard limit enforced.

**Solutions:**
- **Wait until tomorrow:** Automatic reset at UTC midnight (00:00 UTC)
- **Check date:** `cat execution_window.json | grep date` (ensure date is today)
- **Manual override (not recommended):** Delete `execution_window.json` and restart; counter resets to 0 (risky; may trigger LinkedIn's rate-limit detection)

---

### Issue: "429 Too Many Requests / rate limit"

**Error message:**
```
ANOMALY: rate_limit detected. Status: 429, https://linkedin.com/in/...
```

**Root cause:** LinkedIn temporarily blocking requests from this IP/account due to high activity.

**Recovery steps:**
1. Click "Stop Collection" immediately
2. **Wait 2–4 hours** (conservative wait; LinkedIn may unblock faster)
3. Check daily count: `cat execution_window.json | jq .count`
4. If count < 45, you can resume (rate-limit separate from daily limit)
5. If count >= 45, wait until tomorrow
6. **Increase delays** if rate-limit happens again: edit `scraper.py` random.uniform to 4–8s

---

### Issue: "Duplicate profiles in database"

**Symptom:** User reports seeing "Duplicate ignored" message despite pasting unique URLs.

**Root cause:** URL format variations (trailing slash, capitalization, `/in/` variations).

**Check for actual duplicates:**
```sql
SELECT linkedin_url, COUNT(*) FROM linkedin_profiles
GROUP BY linkedin_url HAVING COUNT(*) > 1;
```

Should return 0 rows (UNIQUE constraint is working).

**If duplicates exist:** Bug in URL normalization. Contact developers.

**Clean URL parsing recommendation:**
```python
from urllib.parse import urlparse, urlunparse

def normalize_url(url):
    parsed = urlparse(url)
    # Remove trailing slash
    path = parsed.path.rstrip('/')
    # Lowercase domain
    netloc = parsed.netloc.lower()
    return urlunparse((parsed.scheme, netloc, path, '', '', ''))

# Usage:
url1 = "https://www.linkedin.com/in/john-doe/"
url2 = "https://www.linkedin.com/in/john-doe"
assert normalize_url(url1) == normalize_url(url2)
```

---

### Issue: "Chromium exits with segfault"

**Error message:**
```
[1234:1234:0605/181234.567:ERROR] Segmentation fault (core dumped)
```

**Root causes:**
1. Missing X11 / display libraries
2. glibc version mismatch (PLAYWRIGHT_HOST_PLATFORM_OVERRIDE not set)
3. Low memory (OOM killer)

**Solutions:**
1. Install dependencies:
   ```bash
   apt-get update && apt-get install -y libx11-6 libxrandr2 libfontconfig1 libdbus-1-3
   ```
2. Set PLAYWRIGHT_HOST_PLATFORM_OVERRIDE (if on Ubuntu 26.04):
   ```bash
   export PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64
   ```
3. Ensure 4GB+ RAM available: `free -h`
4. Check system logs: `dmesg | tail -20` (look for OOM messages)

---

### Issue: "Export file is empty or corrupt"

**Symptom:** Downloaded CSV/Excel file is blank or unreadable.

**Root causes:**
1. No profiles in database
2. openpyxl not installed (Excel only)
3. DB connection error during export

**Solutions:**
1. Check DB has profiles: In Streamlit sidebar, see "Database Info: X profiles collected"
2. If 0 profiles, scrape some profiles first
3. For Excel, install openpyxl: `pip install openpyxl`
4. Try CSV first (no external dependency): `export_profiles_to_csv(df)`
5. Check logs: `LOG_LEVEL=DEBUG streamlit run app.py` and retry export

---

### Issue: "Streamlit app won't start"

**Error message:**
```
Address already in use. Use `--port` to specify a different port.
```

Or:
```
ImportError: No module named 'streamlit'
```

**Solutions:**
1. Check port 8501 is free: `lsof -i :8501` (kill if needed: `kill -9 PID`)
2. Verify venv activated: `which python` should show `.../venv/bin/python`
3. Check streamlit installed: `pip list | grep streamlit`
4. Use different port: `streamlit run app.py --server.port 8502`

---

## Testing & Validation

### Unit Tests

Test individual components (database, session manager):

```bash
pytest tests/test_database.py -v
```

**Expectations:**
- Schema creation
- Insert + deduplication
- DataFrame retrieval

```bash
pytest tests/test_session_manager.py -v
```

**Expectations:**
- Session export/import
- Cookie validation

### Integration Tests

Test end-to-end flows (thread spawning, message consumption):

```bash
pytest tests/test_thread_integration.py -v
```

### Manual Validation

1. **Database self-test:**
   ```bash
   python database.py
   # Expected: "All assertions passed. DB layer functional."
   ```

2. **Start app:**
   ```bash
   streamlit run app.py
   # Expected: "Local URL: http://localhost:8501"
   ```

3. **Authenticate:**
   - Click "Launch Interactive Login"
   - Complete login + 2FA
   - Verify `session.json` created: `ls -la session.json`

4. **Scrape test batch (5 URLs):**
   - Paste 5 test URLs into sidebar
   - Click "Start Collection"
   - Monitor status log (should show [SUCCESS] messages)
   - Verify profiles in sidebar "Database Info" widget
   - Check SQLite directly: `sqlite3 linkedin_profiles.db "SELECT COUNT(*) FROM linkedin_profiles;"`

5. **Export test:**
   - Click "Download CSV"
   - Open in text editor (verify UTF-8 encoding, columns correct)
   - Click "Download Excel" (if openpyxl installed)
   - Open in Excel/LibreOffice (verify frozen header, formatting)

### Performance Baseline

Expected throughput (with default 2–5s delays):
- **45 profiles in ~15–20 minutes** (including overhead)
- **Per-profile time:** 15–25 seconds (includes scroll, parse, DB insert)

If slower, check:
- Network latency: `ping linkedin.com` (should be <50ms)
- Disk I/O: `iostat -x 1` (check await %util)
- CPU load: `top` (Python + Chromium should be <200% total)

---

## Environment Variables & Configuration

### `.env` File (Not Committed)

Create by copying `.env.example`:

```bash
cp .env.example .env
```

Edit with your values:

```bash
# LinkedIn Account (for headless login; interactive login preferred for MFA)
LINKEDIN_EMAIL=your-email@example.com
LINKEDIN_PASSWORD=your-password

# [CRITICAL] Playwright Platform Override (Ubuntu 26.04)
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64

# Playwright Browser Cache
PLAYWRIGHT_BROWSERS_PATH=/home/fahim/.cache/ms-playwright

# Debug & Logging
DEBUG=False
LOG_LEVEL=INFO
```

### System Environment Variables

Set before running app (or in shell profile):

```bash
# Display server for Chromium (Xvfb virtual display)
export DISPLAY=:99

# Runtime libraries path (auto-set by environment_config.py if missing)
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu

# Home directory (cache for Chromium)
export HOME=/home/fahim

# Temp directory (Chromium temp files)
export TMPDIR=/tmp
```

### Configuration Constants

In source files (tune after 2+ weeks of successful runs):

**`scraper.py`:**
```python
# Line 55: Daily profile limit
max_profiles_per_day: int = 45  # Change to 50–100 only if experienced user

# Line ~207: Random delays between requests
delay = random.uniform(2, 5)  # Change to (4, 8) if rate-limited
```

**`session_manager.py`:**
```python
# Line 22: MFA timeout (milliseconds)
mfa_timeout: int = 120000  # Increase to 300000 (5 min) if MFA slow
```

**`app.py`:**
```python
# Line 103: Message queue polling interval
if time.time() - st.session_state.last_message_check > 0.1:  # 0.1s = 100ms
```

---

## Legal & Security Notices

⚠️ **Disclaimer:** LinkedIn's Terms of Service prohibit automated scraping. Use of this tool may violate their terms. By using this software, you assume all legal risk.

### LinkedIn ToS Compliance

- **LinkedIn prohibits:** Automated data collection, bot automation, scraping profile data for commercial use
- **This tool:** Provides automation for educational/research purposes; user responsible for compliance
- **Recommended:** Use only for internal lead generation, market research with proper authorization
- **Alternative:** Use LinkedIn's official API (Sales Navigator, Recruiter) if available for your use case

### Rate Limiting & Account Safety

- **Conservative limits:** 45 profiles/day is intentionally low to minimize ban risk
- **Account risk:** Persistent high activity (>100 profiles/day) may result in 24h or permanent ban
- **Recovery:** If banned, wait 24h and try again; permanent bans require appeal to LinkedIn Support

### Credentials & Session Management

- **Never commit .env** with real credentials
- **session.json is sensitive:** Contains authentication cookies (treat as secret)
- `.gitignore` includes: `.env`, `session.json`, `*.db`, `execution_window.json`
- **Backup credentials:** Store LINKEDIN_EMAIL/PASSWORD securely (password manager, not plain text)

### Data Retention & Privacy

- **Your responsibility:** Profiles stored in SQLite are your responsibility to protect
- **GDPR / CCPA:** If collecting from EU/CA users, comply with local privacy laws
  - Implement data retention limits: delete profiles older than 90 days
  - Provide data export on user request
  - Obtain user consent if required by law
- **LinkedIn data:** Profiles scraped from LinkedIn; data ownership reverts to LinkedIn
- **Recommended:** Add data retention policy to your operations manual

### Support & Legal Questions

- **Bug reports:** GitHub Issues (security issues privately via email)
- **Legal questions:** Consult your legal/compliance team or LinkedIn's Platform Security team
- **LinkedIn contact:** platform-security@linkedin.com

---

## Project Structure & Key Files

```
linkedin-scraper/
├── README.md                    # This file
├── .env.example                 # Configuration template (copy to .env)
├── .gitignore                   # Excludes .env, *.db, session.json
├── requirements.txt             # Python dependencies
│
├── app.py                       # Streamlit UI entry point
│   ├─ Session state management
│   ├─ Thread spawning & message consumption
│   ├─ Sidebar authentication & URL input
│   └─ Status log & profile display
│
├── scraper.py                   # Core Playwright logic
│   ├─ ExecutionWindowController (45/day limit)
│   ├─ AnomalyDetector (security monitoring)
│   ├─ scrape_profile_batch() (main async loop)
│   └─ Profile parsing (name, headline, company, etc.)
│
├── session_manager.py           # LinkedIn authentication
│   ├─ launch_browser_for_login() (non-headless)
│   ├─ wait_for_successful_login() (2FA detection)
│   └─ export_session() (save cookies to session.json)
│
├── database.py                  # SQLite operations
│   ├─ init_db() (create schema)
│   ├─ insert_profile() (INSERT OR IGNORE with dedup)
│   └─ get_profiles_df() (fetch all profiles)
│
├── thread_manager.py            # Worker lifecycle
│   ├─ ScraperWorker class
│   ├─ spawn() (start background thread)
│   ├─ get_next_message() (queue consumption)
│   └─ stop() (graceful shutdown)
│
├── environment_config.py        # Linux Chromium environment
│   ├─ get_chromium_environment() (DISPLAY, LD_LIBRARY_PATH)
│   └─ validate_chromium_environment() (check required keys)
│
├── export_helpers.py            # CSV / Excel export
│   ├─ export_profiles_to_csv()
│   └─ export_profiles_to_excel()
│
├── ui_helpers.py                # Streamlit UI utilities
│   ├─ display_validation_sidebar()
│   └─ prepare_profiles_dataframe() (formatting)
│
├── queue_protocol.py            # Message types (IPC)
│   ├─ StatusUpdate (per-profile status)
│   ├─ ProfilePayload (collected profile)
│   ├─ OperationWarning (anomalies)
│   └─ ExecutionComplete (batch done)
│
├── linkedin_profiles.db         # SQLite database (created at runtime)
├── session.json                 # Playwright session storage (created at auth)
├── execution_window.json        # Daily limit state (created at runtime)
│
├── tests/
│   ├─ test_database.py
│   ├─ test_session_manager.py
│   ├─ test_thread_integration.py
│   └─ conftest.py (pytest fixtures)
│
└── .agents/skills/              # Project skills (best practices)
    ├─ playwright-best-practices/
    ├─ developing-with-streamlit/
    ├─ python-performance-optimization/
    └─ pytest-coverage/
```

### File Descriptions

- **app.py** — Streamlit entry point; manages session state, spawns worker, polls message queue
- **scraper.py** — Core async profile scraper; enforces daily limits, detects anomalies
- **session_manager.py** — Handles interactive login with MFA, exports session to JSON
- **database.py** — SQLite schema + insert/query functions; includes self-test
- **thread_manager.py** — Background worker thread lifecycle; message queue consumer
- **environment_config.py** — Maps Linux environment (DISPLAY, libraries) for Chromium
- **export_helpers.py** — CSV/Excel formatters; downloads browser-ready bytes
- **ui_helpers.py** — Streamlit sidebar widgets, profile dataframe preparation
- **queue_protocol.py** — Message classes for thread-safe IPC
- **tests/** — Pytest suite; fixtures, unit tests, integration tests
- **.env.example** — Configuration template; copy to .env and edit
- **requirements.txt** — Python package list (playwright, streamlit, pandas, etc.)

---

## Appendix: Quick Reference

### Essential Commands

```bash
# Setup
git clone https://github.com/yourorg/linkedin-scraper.git && cd linkedin-scraper
python -m venv venv && source venv/bin/activate
export PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64
pip install -r requirements.txt && python -m playwright install

# First run
cp .env.example .env  # Edit with your email/password
python database.py    # Self-test
streamlit run app.py  # Start app

# Interactive login
# In Streamlit UI: Click "Launch Interactive Login"

# Testing
pytest tests/ -v
python database.py    # Verify DB layer

# Database inspection
sqlite3 linkedin_profiles.db ".schema"
sqlite3 linkedin_profiles.db "SELECT COUNT(*) FROM linkedin_profiles;"
```

### API Summary

**Database:**
```python
from database import init_db, insert_profile, get_profiles_df
init_db()
inserted = insert_profile({...})  # Returns True if new, False if duplicate
df = get_profiles_df()
```

**Session:**
```python
from session_manager import SessionManager
manager = SessionManager("session.json")
success = await manager.interactive_login()  # Non-headless browser
```

**Scraper:**
```python
from scraper import scrape_profile_batch, ExecutionWindowController, AnomalyDetector
window = ExecutionWindowController(max_profiles_per_day=45)
detector = AnomalyDetector()
await scrape_profile_batch(urls, queue, window, detector, env, worker_id, stop_event)
```

**Thread:**
```python
from thread_manager import ScraperWorker
worker = ScraperWorker()
worker.spawn(urls, env, window, detector)
msg = worker.get_next_message(timeout=0.05)  # Non-blocking
worker.stop()  # Graceful shutdown
```

---

## Document Metadata

- **Last Updated:** 2026-06-05
- **Version:** 1.0
- **Audience:** Developers, Operations, Security/Compliance
- **Scope:** Setup, operation, schema, troubleshooting, anti-ban mechanics
- **Format:** GitHub Flavored Markdown (GFM); renders on GitHub, GitLab, VS Code, local editors
