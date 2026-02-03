🧠 Job Agent — Automated Internship Tracker

An automated, idempotent job ingestion agent that scrapes internship postings, enriches them with relevance scoring, and syncs them safely into Google Sheets — without overwriting user input or creating duplicates.

Built to solve the problem of missing early internship postings while tracking applications in a clean, user-controlled workflow.

🚨 The Problem

During internship recruiting, I found myself:

Checking job boards daily

Monitoring the same companies repeatedly

Manually tracking postings in spreadsheets

Accidentally missing early applications

Most existing tools either:

overwrite user edits

duplicate jobs

don’t support automation

or don’t give control over relevance filtering

✅ The Solution

This project is a job ingestion agent that:

Pulls live internship postings from GitHub (SimplifyJobs)

Normalizes and de-duplicates jobs deterministically

Scores jobs by relevance using configurable keywords

Respects user-owned spreadsheet fields (e.g. applied status)

Writes updates in bulk to avoid API rate limits

Is safe to run repeatedly (idempotent by design)

🧩 High-Level Architecture
GitHub Job Source (Markdown)
        ↓
HTML Parsing + Normalization
        ↓
Relevance & Confidence Scoring
        ↓
Decision Phase (in memory)
        ↓
Bulk Write to Google Sheets


Key principle:

Decide first. Write once. Never interleave.

🗂️ Project Structure
job-agent/
├── src/
│   ├── scrapers/
│   │   └── simplify_github.py      # GitHub job scraper
│   ├── sheet_reader.py             # Sheets sync + idempotency logic
│   ├── settings.py                 # User preferences loader
│   ├── run_github_ingestion.py     # Entry point
│
├── credentials/
│   └── service_account.json        # Google Sheets service account
│
├── venv/
└── README.md

📊 Google Sheets Schema
User-Owned Columns (never overwritten)

applied (checkbox)

date_applied

application_status

priority

notes

System-Managed Columns

job_id (deterministic SHA-256 hash)

job_title

company

location

job_url

date_posted

relevance_score

role_type

confidence

last_updated

archived

⚙️ User Settings (via Sheets)

The agent reads preferences from a Settings sheet:

Setting	Description
required_job_type	e.g. internship, intern
keywords	relevance keywords
max_days_back	how far back to scan
max_jobs	ingestion cap per run
us_only	location filter
remote_allowed	allow remote roles

This allows non-code customization.

🧠 Relevance Scoring

Each job is scored from 0–100 based on:

Keyword matches (software, ML, AI, etc.)

Role type (internship vs other)

Location relevance (US / Remote)

relevance_score → confidence = score / 100


Confidence represents how strongly the posting matches the user’s intent.

🔐 Idempotency & Safety Guarantees

This system is designed to be safe under retries and failures:

✔ Deterministic job IDs
✔ Bulk writes only (no partial rows)
✔ No user column overwrites
✔ Duplicate detection guard
✔ Crash-safe reruns

If a run fails midway (e.g. API rate limit), rerunning will not duplicate jobs.

☑️ Checkbox Handling

applied is a true checkbox column

Rendered via Sheets data-validation rules

Visibility controlled by a formula:

=IF($A2<>"", FALSE, )


Agent never writes to this column

▶️ How to Run
python src/run_github_ingestion.py


You can safely run this:

daily

multiple times per day

after partial failures

🧪 Example Output
{
  "job_title": "Software Engineer Intern",
  "company": "RTX",
  "location": "Aurora, CO",
  "relevance_score": 100,
  "confidence": 1.0
}

🚀 Why This Matters

This project demonstrates:

Real-world API constraints (rate limits)

Idempotent data pipelines

Safe user/system data separation

Production-style batch processing

Practical automation for recruiting

🔮 Future Improvements

Resume matching for personalized scoring

Email / Slack alerts for high-confidence jobs

Multi-source ingestion (Greenhouse, Lever)

Auto-archive expired roles

Dashboard visualization

📌 Takeaway

This is not just a scraper — it’s a reliable ingestion system built with real-world constraints in mind.
