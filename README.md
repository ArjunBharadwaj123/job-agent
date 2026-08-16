# 🧠 Job Agent — Automated Job-Search Pipeline + JobTrail Dashboard

An end-to-end job-search automation system. It scrapes internship and new-grad postings from multiple job boards, scores each one against your resume, stores everything in a real database, watches your Gmail to automatically update application statuses, and gives you a dashboard ("JobTrail") to browse, filter, and manage the whole pipeline.

It started as a script that synced postings into a Google Sheet. It has since grown into a scheduled, multi-source ingestion pipeline backed by a proper database, an LLM-assisted email tracker, and a web dashboard — all in this one repository.

<img width="1512" alt="JobTrail progress dashboard" src="https://github.com/user-attachments/assets/acf4d273-c268-473a-b5fc-550acbeece88" />

---

## 📦 Repository layout

This is a monorepo with two components that share a single Turso database:

```
job-agent/
├── agent/       # Python ingestion pipeline + Gmail status scanner (the backend)
├── dashboard/   # JobTrail — the Next.js web app (deployed on Vercel)
└── .github/workflows/   # scheduled + on-demand GitHub Actions that run the agent
```

The **agent** runs on a schedule (and on demand) to ingest and score postings and to track application statuses. The **dashboard** is what you actually look at — it reads and writes the same database directly, and its "Refresh jobs" button triggers the agent's workflows through the GitHub API.

---

## 🚨 The problem

During internship recruiting, keeping up manually means:

- Checking multiple job boards every day
- Re-checking the same companies over and over
- Manually logging postings in a spreadsheet
- Losing track of which applications turned into assessments, interviews, or rejections
- Missing early postings because you didn't check in time

## ✅ The solution

Job Agent runs on a schedule and:

- Pulls postings from five job boards plus a curated GitHub list, de-duplicating and normalizing them deterministically
- Scores every posting for relevance using keyword rules blended with resume-based semantic similarity
- Writes to a Turso (libSQL) database with upserts that never clobber fields you've edited yourself
- Reads your Gmail to detect application, assessment, interview, rejection, and offer emails, and updates each job's status automatically
- Sends a push notification after every run summarizing what was found
- Surfaces everything in JobTrail, a web dashboard for tracking your pipeline and tuning settings

---
## 🧰 Tech stack

**Pipeline / backend (`agent/`):** Python, [python-jobspy](https://github.com/speedyapply/JobSpy), BeautifulSoup4, lxml, requests

**Datastore:** [Turso](https://turso.tech/) (hosted libSQL / SQLite-compatible), defined in `agent/schema.sql`

**AI / scoring:** Google Gemini (`gemini-embedding-001`) for resume-vs-description semantic similarity; Groq (`llama-3.3-70b-versatile`) for classifying application-status emails, with a regex/keyword fallback for both

**Integrations:** Gmail API (read-only OAuth) for status tracking, ntfy.sh for push notifications

**Automation:** GitHub Actions — two workflows (scrape + email scan) that run daily at 8am ET and can also be triggered on demand from the dashboard

**Frontend (`dashboard/`):** JobTrail, a Next.js app deployed on Vercel, reading and writing the same Turso database as the pipeline

---

## 🧩 Architecture

```
Ingestion (JobSpy multi-board + GitHub fallback)
 ↓
Normalize + deterministic dedupe (SHA-256 job_id)
 ↓
Score (keywords + resume-semantic blend)
 ↓
Upsert to Turso — system columns only, user-owned columns and locked rows preserved
 ↓
Notify (ntfy.sh)

Gmail scan (independent, daily)
 ↓
Classify email (Groq LLM, rules fallback)
 ↓
Append status_event + update application_status

JobTrail dashboard (Next.js) reads/writes the same Turso DB directly
for status changes, notes, settings, resume, and on-demand AI enrichment.
```

Key principle carried over from the original design: decide first, write once. Scoring and filtering happen in memory before anything is persisted.

---
## 🔀 Data sources

The pipeline ingests from two independent sources so postings keep flowing even if one breaks:

1. **JobSpy multi-board (primary)** — `run_jobspy_ingestion.py` queries Google Jobs, LinkedIn, Indeed, Glassdoor, and ZipRecruiter for every (job title × location) combination configured in settings. A per-board circuit breaker drops a board for the rest of the run after repeated blocks (HTTP 403/429/etc.) instead of hammering it, and a per-board collected-vs-blocked summary is pushed via ntfy after each run.
2. **SimplifyJobs New-Grad-Positions (fallback)** — `run_new_grad_github_ingestion.py` does a keyless HTTP GET against a community-maintained GitHub README. It needs no API keys and runs even when the JobSpy step fails entirely, so an outage never leaves a day with zero new postings.

Jobs from either source share the same scoring, dedup, and Turso upsert path, and any job that has not yet been resume-scored is picked up by a bounded backfill pass on the next run.

<img width="1512" alt="Jobs list with filters" src="https://github.com/user-attachments/assets/134ed9b0-9825-437f-95b3-d8546fcab0b7" />

---

## 🧠 Relevance & resume-based scoring

- A keyword/location/role-type heuristic (`scoring.py`) produces a base 0–100 relevance score.
- If a resume is saved (editable from the dashboard) and `GEMINI_API_KEY` is set, `semantic_scoring.py` embeds both the resume and the job description with Gemini and blends the cosine-similarity score into the base score.
- A keyless "resume-match boost" also nudges scores up when a posting's text overlaps with skills pulled from the resume, so scoring still improves even without an API key.
- `confidence` is simply the blended score normalized to 0–1.
- A bounded per-run backfill re-scores previously unscored jobs, so a temporary Gemini outage never permanently leaves postings under-scored.

Clicking into a job shows AI-generated company and role summaries plus extracted skill tags, enriched lazily on first view:

<img width="1512" alt="Job detail quick view with AI-enriched summary" src="https://github.com/user-attachments/assets/5b422ad1-35bc-4ce2-bc51-6cc2238c638e" />

---
## 📬 Automatic application-status tracking (Gmail → Turso)

- `run_email_status_scan.py` runs daily at 8am America/New_York via GitHub Actions.
- It reads recent Gmail messages with a read-only OAuth scope, matches them to jobs you've applied to, and classifies each into `applied / pending / assessment / interview / rejected / accepted / unknown` using Groq's `llama-3.3-70b-versatile`, falling back to a regex/keyword rules engine if Groq is unavailable or rate-limited.
- It extracts actionable links — assessment platforms like HackerRank/Codility/CodeSignal, or interview schedulers like Calendly/Greenhouse — and surfaces them directly on the job's page.
- Every status change is appended to an immutable `status_events` table and rendered as a timeline.
- Low-confidence classifications are flagged `needs_review` instead of silently changing a job's status.

<img width="1512" alt="Job detail page with application status and timeline" src="https://github.com/user-attachments/assets/8d1e6b4b-bd8c-4c7b-b45d-b8865d3b3f5b" />

---

## 📊 Dashboard — JobTrail (`dashboard/`)

[JobTrail](https://job-dashboard-red.vercel.app/) is a Next.js app that reads and writes the same Turso database as the pipeline. It replaced the Google Sheet as the primary interface and is deployed on Vercel from the `dashboard/` directory of this repo.

- **Progress** — an applications-over-time chart, a pipeline funnel (applied / pending / assessment / interview / accepted / rejected / skipped), and a daily log of activity.
- **Jobs** — a searchable, filterable table of every scraped posting (status, source, relevance score, location) with a "Refresh jobs" button that triggers the GitHub Actions scrape + email scan directly from the browser, plus a quick-view modal for setting a job's status without leaving the list.
- **Settings** — your resume text (which feeds semantic scoring), job-search preferences (titles, locations, earliest start date, max jobs per run, entry-level / US-only / remote-allowed flags), and reusable answers to common application questions.

<img width="1512" alt="Settings page: job-search preferences and saved application answers" src="https://github.com/user-attachments/assets/c38c7950-8611-4a2b-9a07-a16a7a1a0a23" />

---
## 🗄️ Database schema (Turso / libSQL)

Defined in `agent/schema.sql`:

- **`jobs`** — one row per posting. `job_id` is a SHA-256 hash of the normalized `(company, title, location)` triple, so re-scraping the same posting is a safe upsert. System columns (`job_url`, `relevance_score`, `role_type`, `confidence`, …) are refreshed on every scrape; user-owned columns (`applied`, `date_applied`, `application_status`, `priority`, `notes`) are only set on first insert and afterward change only through the dashboard or the email scan. A `locked` flag freezes a row from any further scraper writes.
- **`status_events`** — an append-only history of every status change, including its source (`email` / `manual` / `system`), confidence, and reasoning — rendered as the job's timeline.
- **`email_matches`** — a dedupe/audit table so the same Gmail message is never reclassified twice.
- **`settings`** / **`resume`** — search preferences and resume text, editable from the dashboard.

---

## ⚙️ Automation (GitHub Actions)

Both workflows run **daily at 8:00 AM America/New_York, year-round**. Because GitHub cron only understands UTC, each workflow registers two cron entries (12:00 UTC for EDT summer, 13:00 UTC for EST winter) plus an hour guard that only proceeds when the local Eastern hour is actually `08`, so exactly one run happens per day across the daylight-saving boundary. Both also support manual `workflow_dispatch`, which is how the dashboard's "Refresh jobs" button triggers them.

- **`daily_scrape.yml`** — runs the JobSpy ingestion, then the New-Grad GitHub fallback ingestion (which still runs even if the JobSpy step fails).
- **`daily_email_scan.yml`** — runs the Gmail status scan.

Both workflows execute in `agent/` and post a run summary to ntfy.sh on completion.

---

## 🔐 Idempotency & safety guarantees

- ✔ Deterministic job IDs — every step is safe to rerun any number of times
- ✔ Upserts only ever touch system-owned columns; fields you've edited are never overwritten
- ✔ Locked rows are frozen from further scraper writes entirely
- ✔ Gmail messages are de-duplicated so the same email is never reclassified
- ✔ Every integration (resume, Gemini, Groq, Gmail, ntfy) degrades gracefully when unconfigured instead of failing the run

---
## 🗂️ Project structure

```
job-agent/
├── .github/workflows/
│   ├── daily_scrape.yml            # daily 8am ET scrape (+ on-demand)
│   └── daily_email_scan.yml        # daily 8am ET Gmail status scan (+ on-demand)
├── agent/                          # Python backend
│   ├── src/
│   │   ├── scrapers/
│   │   │   ├── jobspy_source.py     # LinkedIn / Indeed / Glassdoor / ZipRecruiter / Google
│   │   │   └── new_grad_github.py   # SimplifyJobs New-Grad-Positions fallback
│   │   ├── run_jobspy_ingestion.py           # primary ingestion entry point
│   │   ├── run_new_grad_github_ingestion.py  # fallback ingestion entry point
│   │   ├── run_email_status_scan.py          # Gmail status-scan entry point
│   │   ├── scoring.py               # keyword/location/role scoring + resume-match boost
│   │   ├── semantic_scoring.py      # Gemini embeddings similarity
│   │   ├── description_fetcher.py   # fetches full posting descriptions
│   │   ├── email_scan.py            # Gmail scan orchestration
│   │   ├── email_classifier.py      # Groq / rules-based status classification
│   │   ├── gmail_auth.py / gmail_client.py
│   │   ├── store.py                 # Turso/libSQL persistence layer
│   │   ├── normalize.py             # deterministic job_id + settings normalization helpers
│   │   ├── notifier.py              # ntfy.sh push notifications
│   │   ├── init_db.py               # applies schema.sql
│   │   └── mark_skipped.py          # ops helper
│   ├── schema.sql                   # Turso/libSQL schema
│   └── requirements.txt
├── dashboard/                       # JobTrail — Next.js app (Vercel)
│   ├── app/                         # routes + API handlers (jobs, refresh, settings, …)
│   ├── components/                  # tables, charts, modals, status controls
│   ├── lib/                         # Turso client, queries, helpers
│   └── package.json
└── README.md
```

---
## ▶️ Running it locally

### Backend (`agent/`)

Environment variables (put them in `agent/.env`, which is git-ignored):

```
TURSO_DATABASE_URL   # required — libsql://... (hosted) or file:local.db (local dev)
TURSO_AUTH_TOKEN     # required for hosted Turso
GEMINI_API_KEY       # optional — enables resume-based semantic scoring
GROQ_API_KEY         # optional — enables LLM email classification
GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET / GMAIL_REFRESH_TOKEN   # required for the email scan
NTFY_TOPIC           # optional — enables push notifications
```

```bash
cd agent
pip install -r requirements.txt

# first-time schema setup
PYTHONPATH=src python src/init_db.py

# ingest postings
PYTHONPATH=src python src/run_jobspy_ingestion.py
PYTHONPATH=src python src/run_new_grad_github_ingestion.py

# scan Gmail for application-status updates
PYTHONPATH=src python src/run_email_status_scan.py
```

Every entry point is safe to run repeatedly, on a schedule, or after a partial failure — reruns upsert rather than duplicate.

### Dashboard (`dashboard/`)

Environment variables (put them in `dashboard/.env.local`):

```
TURSO_DATABASE_URL   # same database the agent writes to
TURSO_AUTH_TOKEN
GH_DISPATCH_TOKEN    # a GitHub token with 'workflow' scope, so the Refresh button
                     # can dispatch the daily_scrape.yml / daily_email_scan.yml workflows
```

```bash
cd dashboard
npm install
npm run dev          # http://localhost:3000
```

---

## 🔮 Future improvements

- Direct integrations with additional boards (Greenhouse, Lever)
- Auto-archiving of expired/stale postings
- Smarter cross-board dedup for near-duplicate postings
- Additional notification channels (Slack/Discord) alongside ntfy

---

## 📌 Takeaway

This project has grown from a single scraper script into a small production-style system: multi-source ingestion with graceful degradation, a real database with strict user/system column separation, LLM-assisted email understanding, and a dedicated dashboard — now unified in one repo and wired together with scheduled, idempotent automation.
