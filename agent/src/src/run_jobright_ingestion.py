"""
Fallback ingestion runner: pulls recently-posted roles from Jobright's public
landing feed and writes them to Turso.

Runs alongside (and independently of) the JobSpy runner so the daily job still
produces results when the boards/Gemini are unavailable -- this path needs only
a plain HTTP GET and the Turso credentials.

New rows land keyword-scored with semantic_scored = FALSE; the JobSpy runner's
backfill pass resume-scores them newest-first on later runs, since jobright is
an eligible backfill source.
"""

from scrapers.jobright import JobRightScraper
from notifier import notify_summary
import store

# ----------------------------
# Load settings from Turso
# ----------------------------
settings = store.get_settings()
print("Loaded settings:", settings)

# ----------------------------
# Run scraper
# ----------------------------
scraper = JobRightScraper()
raw_jobs = scraper.run(settings)

# 🔒 HARD CAP — REQUIRED
MAX_JOBS = settings["max_jobs"]
raw_jobs = raw_jobs[:MAX_JOBS]

print(f"Processing {len(raw_jobs)} jobs (max_jobs={MAX_JOBS})")

# Descriptions aren't used by this path; drop them before persisting.
for job in raw_jobs:
    job.pop("description", None)

# ----------------------------
# Write to Turso (upsert; user-owned columns and locked rows are preserved)
# ----------------------------
results = store.upsert_jobs(raw_jobs)
print("Results:", results)

# ----------------------------
# Notify (ntfy.sh) — only fires when new jobs were added and NTFY_TOPIC is set
# ----------------------------
notify_summary(results)
