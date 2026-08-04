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

# Pretty board names for the per-board status lines (keys match the
# scraper's site keys / results["board_status"]).
_BOARD_DISPLAY = {
    "google": "Google",
    "linkedin": "LinkedIn",
    "indeed": "Indeed",
    "glassdoor": "Glassdoor",
    "zip_recruiter": "ZipRecruiter",
}


def _format_board_lines(board_status: dict) -> str:
    """
    Renders per-board status into up to two lines, e.g.:
        ✅ Collected: Google 4, LinkedIn 6, Indeed 3
        ⛔ Blocked: Glassdoor (HTTP 400), ZipRecruiter (HTTP 403)
    Boards that simply returned no results (not blocked) are omitted to keep
    the alert short. Returns "" when there's nothing to report.
    """
    if not board_status:
        return ""

    collected, blocked = [], []
    for key, info in board_status.items():
        name = _BOARD_DISPLAY.get(key, key)
        status = info.get("status")
        if status == "collected":
            collected.append(f"{name} {info.get('collected', 0)}")
        elif status == "blocked":
            reason = info.get("reason")
            blocked.append(f"{name} ({reason})" if reason else name)

    lines = []
    if collected:
        lines.append("✅ Collected: " + ", ".join(collected))
    if blocked:
        lines.append("⛔ Blocked: " + ", ".join(blocked))
    return "\n".join(lines)


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

    board_lines = _format_board_lines(results.get("board_status"))
    if board_lines:
        body += "\n" + board_lines

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
