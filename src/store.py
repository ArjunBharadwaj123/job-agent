"""
Turso / libSQL persistence layer -- the datastore that replaced the Google
Sheet. Both the daily scraper and the Gmail status scan write here; the
Next.js dashboard reads/writes the same DB.

Connection is env-driven (TURSO_DATABASE_URL + TURSO_AUTH_TOKEN). A libsql://
or https:// URL connects to hosted Turso; a file: URL (or a bare path) opens a
local libSQL file -- handy for offline development/testing with identical code.

Idempotency: job_id is the PRIMARY KEY, so re-scraping the same posting is an
upsert that touches only system columns and never overwrites the user-owned
fields (applied / date_applied / application_status / priority / notes) or a
row the user has locked.
"""

import os

import libsql_experimental as libsql

# System columns overwritten on a re-scrape (identity + user fields excluded).
_SYSTEM_UPSERT = """
INSERT INTO jobs (
    job_id, job_title, company, location,
    job_url, source, date_posted, date_found,
    relevance_score, role_type, confidence, semantic_scored, last_updated
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(job_id) DO UPDATE SET
    job_url = excluded.job_url,
    source = excluded.source,
    date_posted = excluded.date_posted,
    relevance_score = excluded.relevance_score,
    role_type = excluded.role_type,
    confidence = excluded.confidence,
    -- never downgrade a job that was already resume-scored
    semantic_scored = MAX(jobs.semantic_scored, excluded.semantic_scored),
    last_updated = excluded.last_updated
WHERE jobs.locked = 0
"""


def get_connection():
    """Open a libSQL connection from env (hosted Turso or a local file)."""
    url = os.environ.get("TURSO_DATABASE_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN")
    if not url:
        raise RuntimeError(
            "TURSO_DATABASE_URL must be set (libsql://... for hosted Turso, "
            "or file:local.db for local development)."
        )
    if url.startswith(("libsql://", "https://", "http://")):
        return libsql.connect(database=url, auth_token=token)
    # Local file path (file:jobs.db or a bare path).
    return libsql.connect(url.replace("file:", "", 1))


# ----------------------------
# Schema
# ----------------------------

def init_schema(conn=None, schema_path=None):
    """Apply schema.sql (idempotent -- all CREATE ... IF NOT EXISTS)."""
    conn = conn or get_connection()
    if schema_path is None:
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "schema.sql",
        )
    with open(schema_path, "r", encoding="utf-8") as fh:
        conn.executescript(fh.read())
    conn.commit()
    return conn


# ----------------------------
# Jobs: scraper write path
# ----------------------------

def _to_int(value):
    if isinstance(value, bool):
        return 1 if value else 0
    if value in (None, ""):
        return 0
    return int(value)


def upsert_jobs(raw_jobs, conn=None):
    """
    Insert new jobs / update system columns on existing ones. Mirrors the old
    refresh_jobs contract: returns {"appended", "updated", "locked_skipped"}.
    User-owned columns are only set (to their defaults) on first insert; on
    conflict they are left untouched, and locked rows are not updated at all.
    """
    from datetime import datetime, timezone
    from sheet_reader import generate_job_id

    conn = conn or get_connection()
    if not raw_jobs:
        return {"appended": 0, "updated": 0, "locked_skipped": 0}

    now = datetime.now(timezone.utc).isoformat()
    # The scraper's raw jobs don't carry a job_id or timestamps -- derive them
    # the same way the sheet path did (deterministic identity hash).
    for job in raw_jobs:
        if not job.get("job_id"):
            job["job_id"] = generate_job_id(
                company=job.get("company", ""),
                job_title=job.get("job_title", ""),
                location=job.get("location", ""),
            )
        job.setdefault("date_found", now)
        job.setdefault("last_updated", now)

    ids = [j["job_id"] for j in raw_jobs if j.get("job_id")]
    existing = _existing_ids(conn, ids)
    locked = _locked_ids(conn, ids)

    appended = updated = locked_skipped = 0
    for job in raw_jobs:
        jid = job.get("job_id")
        if not jid:
            continue
        conn.execute(
            _SYSTEM_UPSERT,
            (
                jid,
                job.get("job_title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("job_url", ""),
                job.get("source", ""),
                job.get("date_posted", ""),
                job.get("date_found", ""),
                _to_int(job.get("relevance_score", 0)) if job.get("relevance_score") not in (None, "") else None,
                job.get("role_type", ""),
                job.get("confidence"),
                _to_int(job.get("semantic_scored", 0)),
                job.get("last_updated", ""),
            ),
        )
        if jid not in existing:
            appended += 1
        elif jid in locked:
            locked_skipped += 1
        else:
            updated += 1
    conn.commit()
    return {"appended": appended, "updated": updated, "locked_skipped": locked_skipped}


def _existing_ids(conn, ids):
    found = set()
    for chunk in _chunks(ids, 400):
        placeholders = ",".join("?" * len(chunk))
        rows = conn.execute(
            f"SELECT job_id FROM jobs WHERE job_id IN ({placeholders})", tuple(chunk)
        ).fetchall()
        found.update(r[0] for r in rows)
    return found


def _locked_ids(conn, ids):
    found = set()
    for chunk in _chunks(ids, 400):
        placeholders = ",".join("?" * len(chunk))
        rows = conn.execute(
            f"SELECT job_id FROM jobs WHERE locked = 1 AND job_id IN ({placeholders})",
            tuple(chunk),
        ).fetchall()
        found.update(r[0] for r in rows)
    return found


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


# ----------------------------
# Full-row upsert (migration only -- preserves user-owned columns too)
# ----------------------------

_JOB_COLUMNS = [
    "job_id", "job_title", "company", "location", "job_url", "source",
    "date_posted", "date_found", "relevance_score", "role_type", "confidence",
    "semantic_scored", "archived", "last_updated", "locked", "applied",
    "date_applied", "application_status", "priority", "notes",
    "action_type", "action_url",
]


def replace_job_full(row: dict, conn=None):
    """INSERT OR REPLACE a complete job row including user-owned columns.
    Used only by the one-time Sheet -> Turso migration."""
    conn = conn or get_connection()
    cols = ",".join(_JOB_COLUMNS)
    placeholders = ",".join("?" * len(_JOB_COLUMNS))
    conn.execute(
        f"INSERT OR REPLACE INTO jobs ({cols}) VALUES ({placeholders})",
        tuple(row.get(c) for c in _JOB_COLUMNS),
    )


# ----------------------------
# Settings & resume
# ----------------------------

def set_setting(key, value, conn=None):
    conn = conn or get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, "" if value is None else str(value)),
    )
    conn.commit()


def get_settings(conn=None):
    """Return typed settings, re-using settings_reader's normalizer."""
    from settings_reader import _normalize_settings

    conn = conn or get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    raw = {k: v for k, v in rows}
    return _normalize_settings(raw)


def set_resume(content, conn=None):
    conn = conn or get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO resume (id, content) VALUES (1, ?)",
        (content or "",),
    )
    conn.commit()


def get_resume(conn=None):
    conn = conn or get_connection()
    row = conn.execute("SELECT content FROM resume WHERE id = 1").fetchone()
    return row[0] if row and row[0] else ""


# ----------------------------
# Application status (dashboard + email scan)
# ----------------------------

def get_applied_jobs(conn=None):
    """Jobs the user has engaged with (anything past not_applied)."""
    conn = conn or get_connection()
    rows = conn.execute(
        """
        SELECT job_id, job_title, company, location, application_status,
               date_applied, source, job_url
        FROM jobs
        WHERE applied = 1 OR application_status != 'not_applied'
        """
    ).fetchall()
    cols = [
        "job_id", "job_title", "company", "location", "application_status",
        "date_applied", "source", "job_url",
    ]
    return [dict(zip(cols, r)) for r in rows]


def get_job_status(job_id, conn=None):
    conn = conn or get_connection()
    row = conn.execute(
        "SELECT application_status FROM jobs WHERE job_id = ?", (job_id,)
    ).fetchone()
    return row[0] if row else None


def set_application_status(
    job_id, new_status, source="system", email_id=None,
    email_thread_url=None, confidence=None, reasoning=None,
    action_type=None, action_url=None, needs_review=False,
    conn=None,
):
    """
    Update a job's application_status and append a status_event. When
    needs_review is True the status is NOT changed (low-confidence email
    classification) -- only the event is recorded for the dashboard queue.
    """
    from datetime import datetime, timezone

    conn = conn or get_connection()
    now = datetime.now(timezone.utc).isoformat()
    old = get_job_status(job_id, conn)

    if not needs_review and new_status and new_status != old:
        conn.execute(
            "UPDATE jobs SET application_status = ?, last_updated = ? WHERE job_id = ?",
            (new_status, now, job_id),
        )
        if action_type and action_url:
            conn.execute(
                "UPDATE jobs SET action_type = ?, action_url = ? WHERE job_id = ?",
                (action_type, action_url, job_id),
            )

    conn.execute(
        """
        INSERT INTO status_events (
            job_id, old_status, new_status, source, email_id,
            email_thread_url, confidence, reasoning, action_type, action_url,
            needs_review, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id, old, new_status, source, email_id, email_thread_url,
            confidence, reasoning, action_type, action_url,
            1 if needs_review else 0, now,
        ),
    )
    conn.commit()


# ----------------------------
# Semantic-score backfill (Turso port of semantic_backfill)
# ----------------------------

def get_unscored_jobs(sources=None, limit=25, conn=None):
    """Unscored, unarchived, unlocked jobs newest-first, for resume backfill."""
    conn = conn or get_connection()
    sql = (
        "SELECT job_id, job_url, relevance_score FROM jobs "
        "WHERE semantic_scored = 0 AND archived = 0 AND locked = 0 "
        "AND job_url != '' AND job_url IS NOT NULL"
    )
    params = []
    if sources:
        placeholders = ",".join("?" * len(sources))
        sql += f" AND source IN ({placeholders})"
        params.extend(sources)
    sql += " ORDER BY date_found DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [{"job_id": r[0], "job_url": r[1], "relevance_score": r[2] or 0} for r in rows]


def promote_scores(job_id, relevance_score, confidence, conn=None):
    """Set the blended score + confidence and mark the job semantic_scored."""
    from datetime import datetime, timezone

    conn = conn or get_connection()
    conn.execute(
        """
        UPDATE jobs SET relevance_score = ?, confidence = ?,
               semantic_scored = 1, last_updated = ?
        WHERE job_id = ?
        """,
        (relevance_score, confidence, datetime.now(timezone.utc).isoformat(), job_id),
    )
    conn.commit()


# ----------------------------
# Email dedupe/audit
# ----------------------------

def is_email_processed(email_id, conn=None):
    conn = conn or get_connection()
    row = conn.execute(
        "SELECT 1 FROM email_matches WHERE email_id = ?", (email_id,)
    ).fetchone()
    return row is not None


def mark_email_processed(email_id, job_id, classified_status, confidence, conn=None):
    from datetime import datetime, timezone

    conn = conn or get_connection()
    conn.execute(
        """
        INSERT OR REPLACE INTO email_matches
            (email_id, job_id, classified_status, confidence, processed_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (email_id, job_id, classified_status, confidence,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
