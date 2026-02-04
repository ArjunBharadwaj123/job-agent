from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from scrapers.simplify_github import SimplifyGitHubScraper
from settings_reader import read_settings
from sheet_reader import refresh_jobs, get_sheet_id

# ----------------------------
# Config
# ----------------------------
SPREADSHEET_ID = "1urLLyn7yg6W17l2OsRhonKP6E2wR-8pNF1e8ByKm848"
SHEET_NAME = "Jobs"
CREDENTIALS_FILE = "credentials/service_account.json"

# ----------------------------
# Auth
# ----------------------------
creds = Credentials.from_service_account_file(
    CREDENTIALS_FILE,
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)

service = build("sheets", "v4", credentials=creds)
sheet_id = get_sheet_id(service, SPREADSHEET_ID, SHEET_NAME)
settings = read_settings()
print("Loaded settings:", settings)

# ----------------------------
# Run scraper
# ----------------------------
scraper = SimplifyGitHubScraper()
raw_jobs = scraper.run(settings)

# 🔒 HARD CAP — REQUIRED
MAX_JOBS = settings["max_jobs"]
raw_jobs = raw_jobs[:MAX_JOBS]

print(f"Processing {len(raw_jobs)} jobs (max_jobs={MAX_JOBS})")

# ----------------------------
# Write to sheet
# ----------------------------
results = refresh_jobs(
    raw_jobs=raw_jobs,
    service=service,
    spreadsheet_id=SPREADSHEET_ID,
    sheet_name=SHEET_NAME,
    sheet_id=sheet_id,
)

print("Results:", results)
