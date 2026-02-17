# 🧠 Job Agent — Automated Internship Tracker

An automated, idempotent job ingestion agent that scrapes internship postings, enriches them with relevance scoring, and safely syncs them into Google Sheets — without overwriting user input or creating duplicates.

Built to solve the problem of missing early internship postings while maintaining a clean, user-controlled tracking workflow.

---

## 🚨 The Problem

During internship recruiting, I found myself:

- Checking job boards daily
- Monitoring the same companies repeatedly
- Manually tracking postings in spreadsheets
- Accidentally missing early applications

Most existing tools either:

- Overwrite user edits  
- Create duplicate entries  
- Don’t support automation  
- Don’t allow configurable relevance filtering  

---

## ✅ The Solution

This project is a job ingestion agent that:

- Pulls live internship postings from GitHub (SimplifyJobs repository)
- Normalizes and de-duplicates jobs deterministically
- Scores jobs by relevance using configurable keywords
- Respects user-owned spreadsheet fields (e.g., applied status)
- Writes updates in bulk to avoid API rate limits
- Is safe to run repeatedly (idempotent by design)

---

## 🧩 High-Level Architecture

```
GitHub Job Source (Markdown)
            ↓
HTML Parsing + Normalization
            ↓
Relevance & Confidence Scoring
            ↓
Decision Phase (In Memory)
            ↓
Bulk Write to Google Sheets
```

**Key Principle:**

> Decide first. Write once. Never interleave.

All mutation decisions are computed in memory before a single bulk write occurs.

---

## 🗂️ Project Structure

```
job-agent/
├── src/
│   ├── scrapers/
│   │   └── simplify_github.py        # GitHub job scraper
│   ├── sheet_reader.py               # Sheets sync + idempotency logic
│   ├── settings.py                   # User preferences loader
│   ├── run_github_ingestion.py       # Entry point
│
├── credentials/
│   └── service_account.json          # Google Sheets service account (NOT committed)
│
├── venv/
└── README.md
```

---

## 📊 Google Sheets Schema

### 🔒 User-Owned Columns (Never Overwritten)

- `applied` (checkbox)
- `date_applied`
- `application_status`
- `priority`
- `notes`

### ⚙️ System-Managed Columns

- `job_id` (deterministic SHA-256 hash)
- `job_title`
- `company`
- `location`
- `job_url`
- `date_posted`
- `relevance_score`
- `role_type`
- `confidence`
- `last_updated`
- `archived`

---

## ⚙️ User Settings (Configured via Sheets)

The agent reads preferences from a `Settings` sheet.

| Setting | Description |
|----------|-------------|
| required_job_type | e.g. internship, intern |
| keywords | Relevance keywords (e.g. software, ML, AI) |
| max_days_back | How far back to scan |
| max_jobs | Ingestion cap per run |
| us_only | Location filter |
| remote_allowed | Allow remote roles |

This allows non-code customization of ingestion behavior.

---

## 🧠 Relevance Scoring

Each job is scored from **0–100** based on:

- Keyword matches (software, ML, AI, backend, etc.)
- Role type (internship vs other)
- Location relevance (US / Remote)

```
confidence = relevance_score / 100
```

Confidence represents how strongly the posting matches the user’s intent.

---

## 🔐 Idempotency & Safety Guarantees

This system is designed to be safe under retries and failures.

✔ Deterministic job IDs  
✔ Bulk writes only (no partial rows)  
✔ No user column overwrites  
✔ Duplicate detection guard  
✔ Crash-safe reruns  

If a run fails midway (e.g., API rate limit), rerunning will not duplicate jobs.

---

## ☑️ Checkbox Handling

- `applied` is a true checkbox column
- Rendered via Google Sheets data-validation rules
- Visibility controlled via formula:
  
```
=IF($A2<>"", FALSE, )
```

The agent **never writes to this column**.

---

## ▶️ How to Run

```bash
python src/run_github_ingestion.py
```

You can safely run this:

- Daily
- Multiple times per day
- After partial failures
- On cron / scheduled automation

---

## 🧪 Example Output

```json
{
  "job_title": "Software Engineer Intern",
  "company": "RTX",
  "location": "Aurora, CO",
  "relevance_score": 100,
  "confidence": 1.0
}
```

---

## 🚀 Why This Matters

This project demonstrates:

- Real-world API constraint handling (rate limits)
- Idempotent data pipeline design
- Safe user/system data separation
- Production-style batch processing
- Practical recruiting automation

This is not just a scraper — it is a resilient ingestion system built with real-world constraints in mind.

---

## 🔮 Future Improvements

- Resume matching for personalized scoring
- Email / Slack alerts for high-confidence jobs
- Multi-source ingestion (Greenhouse, Lever, etc.)
- Auto-archive expired roles
- Dashboard visualization

---

## 📌 Takeaway

This project reflects production engineering principles applied to a real-world problem:

Reliable ingestion.  
Deterministic processing.  
User-safe data management.  
Automation with control.
