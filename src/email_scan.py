"""
Daily Gmail status scan: match recent emails to applied jobs, classify the
status, and update the DB. High-confidence changes auto-apply; low-confidence
ones are recorded as needs_review. Idempotent via the email_matches table.
"""

import re

import store
import gmail_client
import email_classifier
from sheet_reader import normalize_company_name
from notifier import notify

CONFIDENCE_THRESHOLD = 0.75

# Pipeline ordering: only advance forward, and rejected/accepted are terminal
# (can be reached from any stage but not overwritten once set).
_ORDER = {
    "not_applied": 0, "applied": 1, "pending": 1,
    "assessment": 2, "interview": 3, "accepted": 4, "rejected": 4,
}
_TERMINAL = {"accepted", "rejected"}


def _transition_allowed(current, new):
    if new in _TERMINAL:
        return current not in _TERMINAL
    return _ORDER.get(new, 0) > _ORDER.get(current, 0)


def _build_company_index(applied_jobs):
    """normalized-company -> list of jobs (most-recent-applied first)."""
    index = {}
    for job in applied_jobs:
        key = normalize_company_name(job.get("company", ""))
        if len(key) < 3:  # skip too-short/generic tokens
            continue
        index.setdefault(key, []).append(job)
    for jobs in index.values():
        jobs.sort(key=lambda j: str(j.get("date_applied") or ""), reverse=True)
    return index


def _match_job(email, company_index):
    """Find the applied job an email is about, or None."""
    blob = normalize_company_name(
        f"{email.get('subject','')} {email.get('from','')} {email.get('body_text','')}"
    )
    # Longest company name first so "openai" wins over a generic short token.
    best_key = None
    for key in sorted(company_index, key=len, reverse=True):
        if re.search(rf"\b{re.escape(key)}\b", blob):
            best_key = key
            break
    if not best_key:
        return None

    candidates = company_index[best_key]
    if len(candidates) == 1:
        return candidates[0]
    # Multiple roles at the company: prefer one whose title appears in the email.
    text = f"{email.get('subject','')} {email.get('body_text','')}".lower()
    for job in candidates:
        title = (job.get("job_title") or "").lower()
        if title and title[:30] in text:
            return job
    return candidates[0]  # else most recently applied


def main():
    applied_jobs = store.get_applied_jobs()
    company_index = _build_company_index(applied_jobs)
    print(f"Tracking {len(applied_jobs)} applied jobs across {len(company_index)} companies")

    messages = gmail_client.recent_messages(days=3)
    print(f"Fetched {len(messages)} recent emails")

    stats = {"updated": 0, "needs_review": 0, "matched": 0, "skipped_unknown": 0}
    lines = []

    for email in messages:
        if store.is_email_processed(email["id"]):
            continue
        job = _match_job(email, company_index)
        if not job:
            continue
        stats["matched"] += 1

        result = email_classifier.classify(email, job)
        status = result["status"]
        conf = result["confidence"]

        if status == "unknown":
            stats["skipped_unknown"] += 1
            store.mark_email_processed(email["id"], job["job_id"], "unknown", conf)
            continue

        current = job.get("application_status", "not_applied")
        if not _transition_allowed(current, status):
            store.mark_email_processed(email["id"], job["job_id"], status, conf)
            continue

        needs_review = conf < CONFIDENCE_THRESHOLD
        store.set_application_status(
            job["job_id"], status, source="email",
            email_id=email["id"], email_thread_url=gmail_client.thread_url(email["thread_id"]),
            confidence=conf, reasoning=result["reasoning"],
            action_type=result.get("action_type"), action_url=result.get("action_url"),
            needs_review=needs_review,
        )
        store.mark_email_processed(email["id"], job["job_id"], status, conf)

        tag = "review" if needs_review else "updated"
        stats["needs_review" if needs_review else "updated"] += 1
        lines.append(f"{job['company']} → {status} ({int(conf*100)}%){' [review]' if needs_review else ''}")

    print("Scan results:", stats)
    for line in lines:
        print("  ", line)

    if stats["updated"] or stats["needs_review"]:
        body = f"{stats['updated']} status update(s), {stats['needs_review']} to review\n" + "\n".join(lines[:10])
        notify(body, title="Application updates", tags="mailbox")

    return stats


if __name__ == "__main__":
    main()
