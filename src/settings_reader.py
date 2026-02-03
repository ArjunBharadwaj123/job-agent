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

    # Max days back (int)
    settings["max_days_back"] = int(
        raw_settings.get("max_days_back", 0)
    )

    # Max jobs (int)
    settings["max_jobs"] = int(
        raw_settings.get("max_jobs", 0)
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
