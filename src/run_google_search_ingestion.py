from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from scrapers.google_search import GoogleSearchScraper
from settings_reader import read_settings
from sheet_reader import refresh_jobs, get_sheet_id
from description_fetcher import fetch_job_description
from semantic_scoring import SemanticScorer
from resume_reader import read_resume
from notifier import notify_summary
from semantic_backfill import backfill_unscored
import scoring

# ----------------------------
# Config
# ----------------------------
SPREADSHEET_ID = "1urLLyn7yg6W17l2OsRhonKP6E2wR-8pNF1e8ByKm848"
SHEET_NAME = "Jobs"
CREDENTIALS_FILE = "credentials/service_account.json"

# ----------------------------
# Auth
# ----------------------------
creds = Credentials.from_service_account_file(
    CREDENTIALS_FILE,
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)

service = build("sheets", "v4", credentials=creds)
sheet_id = get_sheet_id(service, SPREADSHEET_ID, SHEET_NAME)
settings = read_settings()
print("Loaded settings:", settings)

# ----------------------------
# Run scraper
# ----------------------------
scraper = GoogleSearchScraper()
raw_jobs = scraper.run(settings)

# 🔒 HARD CAP — REQUIRED
MAX_JOBS = settings["max_jobs"]
raw_jobs = raw_jobs[:MAX_JOBS]

print(f"Processing {len(raw_jobs)} jobs (max_jobs={MAX_JOBS})")

# ----------------------------
# Description-dependent enrichment: semantic scoring (optional — needs
# resume.txt + GEMINI_API_KEY) and the min_start_date filter (optional —
# needs a min_start_date setting). Google Jobs results already include a
# full description, so we only fall back to fetching the posting page
# ourselves if that field happens to be missing.
# ----------------------------
scorer = SemanticScorer(resume_text=read_resume())
min_start_date = settings.get("min_start_date")

if scorer.available:
    print("Semantic scoring enabled — scoring descriptions against resume.txt")
else:
    print("Semantic scoring skipped (no resume.txt and/or GEMINI_API_KEY set)")

if min_start_date:
    print(f"Start-date filter enabled — excluding jobs starting before {min_start_date}")

if scorer.available or min_start_date:
    kept_jobs = []

    for i, job in enumerate(raw_jobs, start=1):
        description = job.pop("description", "")

        if not description:
            print(f"[{i}/{len(raw_jobs)}] No description from search result, fetching page: {job['company']} - {job['job_title']}")
            fetched = fetch_job_description(job["job_url"])
            description = fetched["description"]
            if not job.get("date_posted") and fetched["date_posted"]:
                job["date_posted"] = fetched["date_posted"]

        if min_start_date:
            # Smart new-grad gate: drops jobs whose start date OR target
            # grad year is before min_start_date, plus explicit "start ASAP"
            # roles; keeps genuinely-undated postings (see scoring docstring).
            if not scoring.passes_start_date_filter(
                job["job_title"], description, min_start_date
            ):
                continue

        if scorer.available:
            semantic_score = scorer.score(description)
            blended_score = scoring.blend_scores(job["relevance_score"], semantic_score)
            job["relevance_score"] = blended_score
            job["confidence"] = scoring.compute_confidence(blended_score, True)
            # Mark whether the resume comparison actually happened this run.
            # None => embedding unavailable (e.g. Gemini credits depleted);
            # the job lands keyword-only and the backfill pass retries it
            # once credits return.
            job["semantic_scored"] = semantic_score is not None

        kept_jobs.append(job)

    print(f"{len(kept_jobs)}/{len(raw_jobs)} jobs kept after description-based filtering/scoring")
    raw_jobs = kept_jobs
else:
    for job in raw_jobs:
        job.pop("description", None)

# ----------------------------
# Write to sheet
# ----------------------------
results = refresh_jobs(
    raw_jobs=raw_jobs,
    service=service,
    spreadsheet_id=SPREADSHEET_ID,
    sheet_name=SHEET_NAME,
    sheet_id=sheet_id,
)

print("Results:", results)

# ----------------------------
# Backfill: resume-score previously-unscored jobs (fail-safe for past runs
# where Gemini credits were unavailable). New jobs above were scored first
# and have priority; this drains the backlog gradually, bounded per run.
# ----------------------------
results["backfilled"] = backfill_unscored(
    scorer=scorer,
    service=service,
    spreadsheet_id=SPREADSHEET_ID,
    sheet_name=SHEET_NAME,
    max_backfill=settings.get("max_backfill", 25),
)

# ----------------------------
# Notify (ntfy.sh) — only fires when new jobs were added and NTFY_TOPIC is set
# ----------------------------
notify_summary(results)
