"""
One-time migration: copy ALL current data from the Google Sheet into Turso.

Moves every Jobs row (including user-owned columns: applied, date_applied,
application_status, priority, notes), the Settings tab, and the Resume tab.
Safe to re-run -- jobs are INSERT OR REPLACE by job_id, settings/resume upsert.

Run: PYTHONPATH=src python src/migrate_sheet_to_turso.py

After this, the daily runner writes to Turso and the Sheet is retired.
"""

import store
from sheet_reader import read_jobs_sheet, _is_true
from settings_reader import read_settings
from resume_reader import read_resume

# Legacy status text -> the dashboard's status vocabulary. Blank/unknown map
# to not_applied (or applied, if the row was marked applied).
_STATUS_ALIASES = {
    "": None,
    "not applied": "not_applied",
    "applied": "applied",
    "pending": "pending",
    "assessment": "assessment",
    "oa": "assessment",
    "online assessment": "assessment",
    "interview": "interview",
    "interviewing": "interview",
    "reject": "rejected",
    "rejected": "rejected",
    "accept": "accepted",
    "accepted": "accepted",
    "offer": "accepted",
}


def _norm_status(raw_status, applied):
    key = (raw_status or "").strip().lower()
    mapped = _STATUS_ALIASES.get(key, None)
    if mapped:
        return mapped
    # Unknown non-empty text: keep it verbatim so nothing is lost.
    if key:
        return raw_status.strip()
    return "applied" if applied else "not_applied"


def migrate_jobs(conn):
    headers, rows, column_map = read_jobs_sheet()

    def cell(row, col):
        idx = column_map.get(col)
        if idx is None or idx >= len(row):
            return ""
        return row[idx]

    count = 0
    for row in rows:
        job_id = cell(row, "job_id")
        if not job_id:
            continue
        applied = _is_true(cell(row, "applied"))
        record = {
            "job_id": job_id,
            "job_title": cell(row, "job_title"),
            "company": cell(row, "company"),
            "location": cell(row, "location"),
            "job_url": cell(row, "job_url"),
            "source": cell(row, "source"),
            "date_posted": cell(row, "date_posted"),
            "date_found": cell(row, "date_found"),
            "relevance_score": _int_or_none(cell(row, "relevance_score")),
            "role_type": cell(row, "role_type"),
            "confidence": _float_or_none(cell(row, "confidence")),
            "semantic_scored": 1 if _is_true(cell(row, "semantic_scored")) else 0,
            "archived": 1 if _is_true(cell(row, "archived")) else 0,
            "last_updated": cell(row, "last_updated"),
            "locked": 1 if _is_true(cell(row, "locked")) else 0,
            "applied": 1 if applied else 0,
            "date_applied": cell(row, "date_applied"),
            "application_status": _norm_status(cell(row, "application_status"), applied),
            "priority": cell(row, "priority"),
            "notes": cell(row, "notes"),
            "action_type": None,
            "action_url": None,
        }
        store.replace_job_full(record, conn)
        count += 1
    conn.commit()
    return count, len(rows)


def migrate_settings(conn):
    settings = read_settings()

    def to_str(value):
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return ""
        return str(value)

    for key, value in settings.items():
        store.set_setting(key, to_str(value), conn)
    return len(settings)


def migrate_resume(conn):
    content = read_resume()
    store.set_resume(content, conn)
    return len(content)


def _int_or_none(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _float_or_none(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def main():
    conn = store.init_schema()  # ensure tables exist first

    migrated, total = migrate_jobs(conn)
    print(f"Jobs: migrated {migrated}/{total} rows")

    n_settings = migrate_settings(conn)
    print(f"Settings: migrated {n_settings} keys")

    n_resume = migrate_resume(conn)
    print(f"Resume: migrated {n_resume} chars")

    # Sanity: row count in the DB
    db_count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    print(f"Verification: jobs table now holds {db_count} rows")


if __name__ == "__main__":
    main()
