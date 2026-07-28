"""
Sends a one-line summary of an ingestion run to the user's phone via
ntfy.sh (https://ntfy.sh) -- a free, account-less push service. The user
subscribes their phone to a private topic; we POST the summary to that
topic's URL.

Degrades gracefully, matching the rest of the pipeline: if no topic is
configured, or the run added no new jobs, or the HTTP call fails, this
no-ops (with a printed reason) rather than raising. A failed notification
must never fail the ingestion run.
"""

import os

import requests

NTFY_BASE_URL = "https://ntfy.sh"
NTFY_TOPIC_ENV = "NTFY_TOPIC"
REQUEST_TIMEOUT = 10


def notify_summary(results: dict, topic: str = None) -> None:
    """
    Pushes "<N> added, <M> updated." to the configured ntfy topic.

    No-ops when:
      - no topic is configured (NTFY_TOPIC unset / no `topic` arg), or
      - results["appended"] == 0 (cadence: only notify on new jobs).
    """
    topic = topic or os.environ.get(NTFY_TOPIC_ENV)
    if not topic:
        print(f"Notification skipped ({NTFY_TOPIC_ENV} not set)")
        return

    appended = results.get("appended", 0)
    if appended == 0:
        print("Notification skipped (no new jobs added)")
        return

    updated = results.get("updated", 0)
    body = f"{appended} added, {updated} updated."

    backfilled = results.get("backfilled", 0)
    if backfilled:
        body += f" ({backfilled} resume-scored)"

    try:
        response = requests.post(
            f"{NTFY_BASE_URL}/{topic}",
            data=body.encode("utf-8"),
            headers={
                "Title": "Job Agent",
                "Tags": "briefcase",
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Notification failed: {exc}")
        return

    print(f"Notification sent: {body}")
