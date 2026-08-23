"""
Daily scrape -> score -> Turso. Repointed from the Google Sheet to the libSQL
datastore (see store.py). The scraping + scoring pipeline is unchanged; only
persistence (settings, resume, write, backfill) now goes through `store`.
"""

from scrapers.jobspy_source import JobSpyScraper
from description_fetcher import fetch_job_description
from semantic_scoring import SemanticScorer
from notifier import notify_summary
import scoring
import store

# Sources eligible for resume-score backfill (JobSpy boards + legacy sources).
BACKFILL_SOURCES = [
    "linkedin", "indeed", "glassdoor", "zip_recruiter", "google",
    "google_search", "new_grad_github", "jobright",
]

# ----------------------------
# Load settings + resume from Turso
# ----------------------------
settings = store.get_settings()
print("Loaded settings:", settings)

# ----------------------------
# Run scraper
# ----------------------------
scraper = JobSpyScraper()
raw_jobs = scraper.run(settings)

# 🔒 HARD CAP — REQUIRED
MAX_JOBS = settings["max_jobs"]
raw_jobs = raw_jobs[:MAX_JOBS]
print(f"Processing {len(raw_jobs)} jobs (max_jobs={MAX_JOBS})")

# ----------------------------
# Description-dependent enrichment: semantic scoring (optional — needs resume
# + GEMINI_API_KEY) and the min_start_date filter. JobSpy no longer pre-fetches
# LinkedIn descriptions, so this fetches the posting page for jobs missing one.
# ----------------------------
resume_text = store.get_resume()
scorer = SemanticScorer(resume_text=resume_text)
# Keyless resume-match boost: reward jobs that ask for the candidate's skills
# (works with or without Gemini semantic scoring).
resume_skill_set = scoring.resume_skills(resume_text)
if resume_skill_set:
    print(f"Resume-match boost enabled ({len(resume_skill_set)} skills from resume)")
min_start_date = settings.get("min_start_date")

if scorer.available:
    print("Semantic scoring enabled — scoring descriptions against resume")
else:
    print("Semantic scoring skipped (no resume and/or GEMINI_API_KEY set)")

if min_start_date:
    print(f"Start-date filter enabled — excluding jobs starting before {min_start_date}")

if scorer.available or min_start_date:
    kept_jobs = []
    for i, job in enumerate(raw_jobs, start=1):
        description = job.pop("description", "")
        if not description:
            print(f"[{i}/{len(raw_jobs)}] Fetching description: {job['company']} - {job['job_title']}")
            fetched = fetch_job_description(job["job_url"])
            description = fetched["description"]
            if not job.get("date_posted") and fetched["date_posted"]:
                job["date_posted"] = fetched["date_posted"]

        if min_start_date and not scoring.passes_start_date_filter(
            job["job_title"], description, min_start_date
        ):
            continue

        if scorer.available:
            semantic_score = scorer.score(description)
            blended = scoring.blend_scores(job["relevance_score"], semantic_score)
            job["relevance_score"] = blended
            job["confidence"] = scoring.compute_confidence(blended, True)
            job["semantic_scored"] = semantic_score is not None

        # Resume-match boost (uses the full description here).
        job["relevance_score"] = min(
            100,
            job["relevance_score"]
            + scoring.resume_match_boost(resume_skill_set, f"{job['job_title']} {description}"),
        )

        kept_jobs.append(job)

    print(f"{len(kept_jobs)}/{len(raw_jobs)} jobs kept after description-based filtering/scoring")

    # These jobs are now fully scored (semantic blend + resume boost), so we can
    # safely drop anything below the relevance threshold before it reaches the DB.
    scored_count = len(kept_jobs)
    kept_jobs = [
        j for j in kept_jobs if (j.get("relevance_score") or 0) >= scoring.MIN_RELEVANCE_SCORE
    ]
    dropped = scored_count - len(kept_jobs)
    if dropped:
        print(f"Dropped {dropped} job(s) scoring below {scoring.MIN_RELEVANCE_SCORE} (not inserted)")
    raw_jobs = kept_jobs
else:
    # No description pass -- apply the resume boost on the title alone.
    for job in raw_jobs:
        job["relevance_score"] = min(
            100,
            job["relevance_score"] + scoring.resume_match_boost(resume_skill_set, job["job_title"]),
        )
        job.pop("description", None)

# ----------------------------
# Write to Turso (upsert; user-owned columns and locked rows are preserved)
# ----------------------------
results = store.upsert_jobs(raw_jobs)
print("Results:", results)

# ----------------------------
# Backfill: resume-score previously-unscored jobs (fail-safe for past runs
# where Gemini credits were unavailable), newest-first, bounded per run.
# ----------------------------
results["backfilled"] = 0
results["archived_low_score"] = 0
if scorer.available:
    candidates = store.get_unscored_jobs(
        sources=BACKFILL_SOURCES, limit=settings.get("max_backfill", 25)
    )
    print(f"Backfill: {len(candidates)} unscored jobs to process")
    for job in candidates:
        fetched = fetch_job_description(job["job_url"])
        description = fetched["description"]
        if not description:
            continue
        semantic_score = scorer.score(description)
        if semantic_score is None:
            print("Backfill stopped early (embedding unavailable)")
            break
        blended = scoring.blend_scores(job["relevance_score"], semantic_score)
        # Now fully scored: archive (hide) anything still below the threshold
        # instead of surfacing it on the board.
        if blended < scoring.MIN_RELEVANCE_SCORE:
            store.archive_job(job["job_id"])
            results["archived_low_score"] += 1
        else:
            store.promote_scores(job["job_id"], blended, scoring.compute_confidence(blended, True))
            results["backfilled"] += 1
    print(f"Backfill: {results['backfilled']} job(s) resume-scored this run")
    if results["archived_low_score"]:
        print(
            f"Backfill: archived {results['archived_low_score']} job(s) scoring "
            f"below {scoring.MIN_RELEVANCE_SCORE}"
        )

# ----------------------------
# Notify (ntfy.sh) — per-board collected-vs-blocked status + counts
# ----------------------------
results["board_status"] = getattr(scraper, "board_status", {})
notify_summary(results)
