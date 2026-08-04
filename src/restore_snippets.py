"""
One-off recovery: restore the `description_snippet` column (and any stray
notes/priority/date_applied that lived on a dropped duplicate row) from the
Google Sheet into Turso.

Non-destructive: every write is fill-only-if-empty, so it never overwrites a
value already in Turso (protecting any edits made in the dashboard) and never
re-adds the collapsed duplicate rows. Safe to re-run.

Run: PYTHONPATH=src python src/restore_snippets.py
"""

import store
from sheet_reader import read_jobs_sheet

# Columns to recover, all fill-only-if-empty. description_snippet is the real
# loss; the rest recover stray cells from dropped duplicate rows.
_RECOVER = ["description_snippet", "notes", "priority", "date_applied"]


def main():
    headers, rows, column_map = read_jobs_sheet()

    def cell(row, col):
        idx = column_map.get(col)
        if idx is None or idx >= len(row):
            return ""
        return (row[idx] or "").strip()

    conn = store.get_connection()
    filled = {c: 0 for c in _RECOVER}

    for row in rows:
        job_id = cell(row, "job_id")
        if not job_id:
            continue
        for col in _RECOVER:
            value = cell(row, col)
            if not value:
                continue
            cur = conn.execute(
                f"UPDATE jobs SET {col} = ? "
                f"WHERE job_id = ? AND ({col} IS NULL OR {col} = '')",
                (value, job_id),
            )
            # rowcount is 1 only when a NULL/empty cell was actually filled.
            if getattr(cur, "rowcount", 0) and cur.rowcount > 0:
                filled[col] += cur.rowcount

    # Consistency fix: a unique job that was applied in ANY sheet copy should be
    # applied=1. The migration's last-duplicate-wins arbitrarily kept the
    # non-applied copy of a few duplicates, dropping their flag (these are
    # distinct jobs, NOT duplicate inflation).
    applied_ids = {
        cell(r, "job_id")
        for r in rows
        if cell(r, "job_id") and str(cell(r, "applied")).upper() == "TRUE"
    }
    applied_fixed = 0
    for job_id in applied_ids:
        cur = conn.execute(
            "UPDATE jobs SET applied = 1 WHERE job_id = ? AND applied = 0",
            (job_id,),
        )
        if getattr(cur, "rowcount", 0) and cur.rowcount > 0:
            applied_fixed += cur.rowcount
    print(f"applied flag recovered on {applied_fixed} distinct jobs")

    conn.commit()

    print("Recovered (filled where Turso was empty):")
    for col in _RECOVER:
        print(f"  {col}: {filled[col]}")

    # Report resulting coverage.
    for col in _RECOVER:
        n = conn.execute(
            f"SELECT COUNT(*) FROM jobs WHERE {col} IS NOT NULL AND {col} != ''"
        ).fetchone()[0]
        print(f"  -> {col} now populated in {n} rows")


if __name__ == "__main__":
    main()
