from datetime import datetime

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


# ----------------------------
# Configuration
# ----------------------------

SPREADSHEET_ID = "1urLLyn7yg6W17l2OsRhonKP6E2wR-8pNF1e8ByKm848"
SETTINGS_SHEET_NAME = "Settings"
CREDENTIALS_FILE = "credentials/service_account.json"


# ----------------------------
# Public API
# ----------------------------

def read_settings():
    """
    Reads user preferences from the Settings sheet
    and returns a normalized settings dict.
    """

    creds = Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )

    service = build("sheets", "v4", credentials=creds)

    response = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=SPREADSHEET_ID,
            range=SETTINGS_SHEET_NAME,
        )
        .execute()
    )

    values = response.get("values", [])

    if not values or len(values) < 2:
        raise RuntimeError("Settings sheet is empty or malformed")

    # Expect header: key | value
    raw_settings = {}

    for row in values[1:]:
        if len(row) < 2:
            continue

        key = row[0].strip()
        value = row[1].strip()

        if not key:
            continue

        raw_settings[key] = value

    return _normalize_settings(raw_settings)


# ----------------------------
# Internal helpers
# ----------------------------

def _normalize_settings(raw_settings: dict):
    """
    Converts raw string settings into typed values.
    """

    settings = {}

    # Required job type (comma-separated list)
    job_type_raw = raw_settings.get("required_job_type", "")
    settings["required_job_type"] = [
        jt.strip().lower()
        for jt in job_type_raw.split(",")
        if jt.strip()
]

    # Keywords (comma-separated list)
    keywords_raw = raw_settings.get("keywords", "")
    settings["keywords"] = [
        k.strip().lower()
        for k in keywords_raw.split(",")
        if k.strip()
    ]

    # Job titles to search for, e.g. "Software Engineer, Data Analyst"
    # (comma-separated list)
    job_titles_raw = raw_settings.get("job_titles", "")
    settings["job_titles"] = [
        jt.strip()
        for jt in job_titles_raw.split(",")
        if jt.strip()
    ]

    # Locations to search in, e.g. "Chicago, New York, Remote"
    # (comma-separated list)
    locations_raw = raw_settings.get("locations", "")
    settings["locations"] = [
        loc.strip()
        for loc in locations_raw.split(",")
        if loc.strip()
    ]

    # Entry-level only flag (bool) — hard-filter out non-entry-level jobs
    # rather than just scoring them lower.
    settings["entry_level_only"] = raw_settings.get(
        "entry_level_only", "false"
    ).strip().lower() == "true"

    # Earliest acceptable job start date, e.g. "2027-05" or "2027-05-01".
    # Only excludes jobs where a start date was actually found in the
    # description AND it's earlier than this -- jobs with no stated start
    # date pass through untouched (Google Search source only).
    settings["min_start_date"] = _parse_date_setting(
        raw_settings.get("min_start_date", "")
    )

    # Max days back (int)
    settings["max_days_back"] = int(
        raw_settings.get("max_days_back", 0)
    )

    # Max jobs (int)
    settings["max_jobs"] = int(
        raw_settings.get("max_jobs", 0)
    )

    # Max jobs to resume-score-backfill per run (int). Bounds how much of
    # the unscored backlog each run drains, so a large backlog doesn't blow
    # up run time / Gemini cost. Defaults to 25 when unset.
    settings["max_backfill"] = int(
        raw_settings.get("max_backfill", 25)
    )

    # US-only flag (bool)
    settings["us_only"] = raw_settings.get(
        "us_only", "false"
    ).strip().lower() == "true"

    # Remote allowed flag (bool)
    settings["remote_allowed"] = raw_settings.get(
        "remote_allowed", "false"
    ).strip().lower() == "true"

    return settings


def _parse_date_setting(value: str):
    """
    Parses a date setting in "YYYY-MM-DD" or "YYYY-MM" form. Returns None
    for an empty/missing value or anything unparseable, rather than
    raising -- an invalid date setting should mean "no filter," not a
    crashed run.
    """
    value = value.strip()
    if not value:
        return None

    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return None
