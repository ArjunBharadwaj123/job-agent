"""
Mark passed-over jobs as "skipped".

Any job still `not_applied` that was found BEFORE your most recent application
is one you effectively moved past -- set it to `skipped`. Newer not_applied
jobs (found on/after your last apply date) stay actionable.

Non-destructive: only touches `not_applied` rows; never changes applied jobs or
any other status. Idempotent (re-run marks 0 more). date_found is an ISO
timestamp, so a lexical `<` against the cutoff date is a correct date compare.

Run: PYTHONPATH=src python src/mark_skipped.py
"""

from datetime import date, datetime, timezone

import store


def _parse_mdy(s):
    try:
        m, d, y = [int(x) for x in s.strip().split("/")]
        return date(y, m, d)
    except (ValueError, AttributeError):
        return None


def main():
    conn = store.get_connection()

    applied = [
        _parse_mdy(r[0])
        for r in conn.execute(
            "SELECT date_applied FROM jobs WHERE applied = 1 AND date_applied != ''"
        ).fetchall()
    ]
    applied = [d for d in applied if d]
    if not applied:
        print("No applications found; nothing to skip.")
        return

    cutoff = max(applied).isoformat()  # e.g. "2026-08-03"
    print(f"Most recent application: {cutoff}")

    cur = conn.execute(
        """
        UPDATE jobs SET application_status = 'skipped', last_updated = ?
        WHERE application_status = 'not_applied'
          AND date_found IS NOT NULL AND date_found != ''
          AND date_found < ?
        """,
        (datetime.now(timezone.utc).isoformat(), cutoff),
    )
    conn.commit()
    n = getattr(cur, "rowcount", 0) or 0
    print(f"Marked {n} job(s) as skipped (not_applied + found before {cutoff}).")
    still = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE application_status = 'not_applied'"
    ).fetchone()[0]
    print(f"Remaining not_applied: {still}")


if __name__ == "__main__":
    main()
