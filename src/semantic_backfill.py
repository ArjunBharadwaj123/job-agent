"""
Resume-scoring backfill: a fail-safe for when Gemini credits are
unavailable.

New jobs are always semantic-scored inline at ingestion time (see
run_google_search_ingestion.py) -- they have priority. But when the
embedding API is down/unfunded, those jobs land in the sheet with
`semantic_scored = FALSE` and a keyword-only relevance_score. Once credits
return, this pass fills them in: it walks the unscored rows newest-first,
re-fetches each posting's description, scores it against the resume, and
promotes relevance_score / confidence / semantic_scored.

Bounded per run (max_backfill) so a large backlog drains gradually without
blowing up run time or Gemini cost. Stops early the moment an embedding
call fails again -- if credits ran out mid-pass there's no point hammering
the API for the rest of the batch.
"""

from datetime import datetime, timezone

import scoring
from description_fetcher import fetch_job_description
from sheet_reader import (
    read_jobs_sheet,
    build_job_index,
    update_job_row,
    _is_true,
)

DEFAULT_MAX_BACKFILL = 25

# Only backfill jobs from these sources. The legacy GitHub/SimplifyJobs
# backlog (~1k rows) is intentionally excluded: those postings are old,
# often expired, and re-fetching them mostly fails -- backfill effort
# belongs on current, re-fetchable google_search jobs. Set to None to
# backfill every source.
BACKFILL_SOURCES = {"google_search"}


def backfill_unscored(
    scorer,
    service,
    spreadsheet_id,
    sheet_name,
    max_backfill: int = DEFAULT_MAX_BACKFILL,
    sources=BACKFILL_SOURCES,
) -> int:
    """
    Scores up to `max_backfill` previously-unscored jobs. Returns the count
    actually backfilled. No-ops (returns 0) when semantic scoring isn't
    available at all (no resume / no API key).

    `sources` restricts which job sources are eligible (None = all).
    """
    if not scorer.available:
        print("Backfill skipped (semantic scoring unavailable)")
        return 0

    _, rows, column_map = read_jobs_sheet()
    job_index, jobs = build_job_index(rows, column_map)

    def cell(row, col):
        idx = column_map.get(col)
        if idx is None or idx >= len(row):
            return ""
        return row[idx]

    # Candidate = has identity + a URL to re-fetch, not archived, not
    # locked, and not already semantic-scored.
    candidates = []
    for row in rows:
        job_id = cell(row, "job_id")
        job_url = cell(row, "job_url")
        if not job_id or not job_url:
            continue
        if _is_true(cell(row, "archived")) or _is_true(cell(row, "locked")):
            continue
        if _is_true(cell(row, "semantic_scored")):
            continue
        if sources is not None and cell(row, "source") not in sources:
            continue
        candidates.append(row)

    if not candidates:
        print("Backfill: no unscored jobs")
        return 0

    # Newest first -- fresh jobs get resume-scored before the old backlog.
    # date_found is an ISO timestamp, so string sort == chronological.
    candidates.sort(key=lambda r: str(cell(r, "date_found")), reverse=True)

    print(f"Backfill: {len(candidates)} unscored jobs; processing up to {max_backfill}")

    now = datetime.now(timezone.utc).isoformat()
    backfilled = 0

    for row in candidates[:max_backfill]:
        job_id = cell(row, "job_id")

        fetched = fetch_job_description(cell(row, "job_url"))
        description = fetched["description"]
        if not description:
            # Posting expired / blocked scraping / not HTML. Leave it
            # FALSE; a future run retries it.
            continue

        semantic_score = scorer.score(description)
        if semantic_score is None:
            # Non-empty description but scoring returned nothing -> the
            # embedding call failed (credits gone again). Stop the pass.
            print("Backfill stopped early (embedding unavailable)")
            break

        try:
            keyword_score = int(cell(row, "relevance_score") or 0)
        except (TypeError, ValueError):
            keyword_score = 0

        blended = scoring.blend_scores(keyword_score, semantic_score)

        update_job_row(
            service=service,
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            job_id=job_id,
            updates={
                "relevance_score": blended,
                "confidence": scoring.compute_confidence(blended, True),
                "semantic_scored": True,
                "last_updated": now,
            },
            job_index=job_index,
            jobs=jobs,
            column_map=column_map,
        )
        backfilled += 1

    print(f"Backfill: {backfilled} job(s) resume-scored this run")
    return backfilled
