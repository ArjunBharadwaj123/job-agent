"""
Reads the user's resume from a 'Resume' tab in the same spreadsheet that
holds Settings and Jobs.

This is the single source of truth for semantic scoring's resume text: the
user updates their resume by editing that tab, no code change / secret edit
required. A missing or empty tab is not an error -- it just means semantic
scoring is unavailable for the run (see semantic_scoring.SemanticScorer),
so read_resume() returns "" instead of raising in that case.
"""

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


# ----------------------------
# Configuration
# ----------------------------

SPREADSHEET_ID = "1urLLyn7yg6W17l2OsRhonKP6E2wR-8pNF1e8ByKm848"
RESUME_SHEET_NAME = "Resume"
CREDENTIALS_FILE = "credentials/service_account.json"


def read_resume():
    """
    Reads resume text from the 'Resume' tab and returns it as a single
    string (cells joined by spaces, rows joined by newlines).

    Returns "" if the tab is missing/empty or the read fails -- a missing
    resume just disables semantic scoring, it is not a fatal error.
    """
    creds = Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )

    service = build("sheets", "v4", credentials=creds)

    try:
        response = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=SPREADSHEET_ID,
                range=RESUME_SHEET_NAME,
            )
            .execute()
        )
    except Exception as exc:  # tab may not exist yet, or transient API error
        print(f"Could not read '{RESUME_SHEET_NAME}' tab: {exc}")
        return ""

    values = response.get("values", [])

    # values is a list of rows, each a list of cell strings. Flatten into a
    # single blob -- structure/formatting doesn't matter for embedding.
    lines = [" ".join(cell for cell in row).strip() for row in values]
    return "\n".join(line for line in lines if line).strip()
