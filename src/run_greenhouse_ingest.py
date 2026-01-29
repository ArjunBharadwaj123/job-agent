from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from scrapers.greenhouse import GreenhouseScraper
from matching.matcher import filter_jobs
from matching.filters import USER_PREFERENCES
from sheet_reader import (
    refresh_jobs,
    get_sheet_id,
    SPREADSHEET_ID,
    SHEET_NAME,
    CREDENTIALS_FILE,
)

# ──────────────────────────────
# Greenhouse companies (name → slug)
# ──────────────────────────────
GREENHOUSE_COMPANIES = {
    "Airbnb": "airbnb",
    "Stripe": "stripe",
    "Adyen": "adyen",
    "Pinterest": "pinterest",
    "Squarespace": "squarespace",
    "Vimeo": "vimeo",
    "Warby Parker": "warbyparker",
    "Betterment": "betterment",
    "TripAdvisor": "tripadvisor",
}

# ──────────────────────────────
# Auth
# ──────────────────────────────
creds = Credentials.from_service_account_file(
    CREDENTIALS_FILE,
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
service = build("sheets", "v4", credentials=creds)

sheet_id = get_sheet_id(service, SPREADSHEET_ID, SHEET_NAME)

# ──────────────────────────────
# Scrape ALL companies
# ──────────────────────────────
all_raw_jobs = []

for company_name, slug in GREENHOUSE_COMPANIES.items():
    try:
        print(f"\n🔍 Scraping Greenhouse: {company_name}")

        scraper = GreenhouseScraper(slug)
        jobs = scraper.fetch_jobs()

        print(f"  → {len(jobs)} jobs scraped")

        all_raw_jobs.extend(jobs)

    except Exception as e:
        print(f"⚠️ Failed to scrape {company_name}: {e}")

print(f"\n📦 Total jobs scraped: {len(all_raw_jobs)}")

# ──────────────────────────────
# Filter (agent intent layer)
# ──────────────────────────────
filtered_jobs = filter_jobs(all_raw_jobs, USER_PREFERENCES)

print(f"🎯 Jobs after filtering: {len(filtered_jobs)}")

# ──────────────────────────────
# Ingest into Sheets
# ──────────────────────────────
results = refresh_jobs(
    raw_jobs=filtered_jobs,
    service=service,
    spreadsheet_id=SPREADSHEET_ID,
    sheet_name=SHEET_NAME,
    sheet_id=sheet_id,
)

print("\n✅ Ingestion complete:")
print(results)
