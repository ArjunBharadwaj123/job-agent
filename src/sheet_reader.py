from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import re
import hashlib
from scrapers.greenhouse import GreenhouseScraper


# ----------------------------
# Configuration
# ----------------------------

SPREADSHEET_ID = "1urLLyn7yg6W17l2OsRhonKP6E2wR-8pNF1e8ByKm848"
SHEET_NAME = "Jobs"
CREDENTIALS_FILE = "credentials/service_account.json"

REQUIRED_COLUMNS = {
    "job_id",        # identity / primary key
    "job_title",    # identity (immutable after creation)
    "company",      # identity (immutable after creation)
    "location",     # identity (immutable after creation)
    "applied",      # user intent gate
    "locked",       # system freeze switch
    "last_updated", # agent heartbeat
}

# ----------------------------
# Write Permissions
# ----------------------------

# Columns the agent is allowed to write to (metadata only)
SYSTEM_WRITABLE_COLUMNS = {
    "job_url",          # links can change
    "source",           # scraper/source metadata
    "date_posted",      # may be refined
    "relevance_score",  # computed by agent
    "role_type",        # classification
    "confidence",       # agent confidence
    "archived",         # agent lifecycle control
    "last_updated",     # always updated
}

CONTENT_UPDATE_COLUMNS = {
    "job_url",
    "source",
    "date_posted",
}

# Columns that must NEVER be written by the agent
USER_OWNED_COLUMNS = {
    "applied",
    "date_applied",
    "application_status",
    "priority",
    "notes",
}


# ----------------------------
# Read Jobs Sheet
# ----------------------------

def read_jobs_sheet():
    """
    Reads the Jobs sheet safely and returns:
    - headers (list)
    - rows (list of lists)
    - column_map (dict: column_name -> index)
    """

    # 1. Authenticate using service account
    creds = Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )

    service = build("sheets", "v4", credentials=creds)

    # 2. Read entire sheet
    range_name = f"{SHEET_NAME}"
    response = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=range_name)
        .execute()
    )

    values = response.get("values", [])

    if not values:
        raise RuntimeError("Jobs sheet is empty")

    # 3. Extract headers
    headers = values[0]

    # 4. Build column map
    column_map = {header: idx for idx, header in enumerate(headers)}

    # 5. Validate required columns
    missing = REQUIRED_COLUMNS - column_map.keys()
    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")

    # 6. Remaining rows are job data
    rows = values[1:]

    return headers, rows, column_map

def build_job_index(rows, column_map):
    """
    Builds:
    - job_index: job_id -> row_index (1-based, matching Sheets)
    - jobs: job_id -> job metadata dict
    """

    job_index = {}
    jobs = {}

    for i, row in enumerate(rows):
        # Sheet row number = header row (1) + data offset (i + 1)
        sheet_row_index = i + 2

        # Defensive reads (cells may be missing)
        job_id = row[column_map["job_id"]] if column_map["job_id"] < len(row) else ""
        applied = (
            row[column_map["applied"]].upper() == "TRUE"
            if column_map["applied"] < len(row)
            else False
        )
        locked = (
            row[column_map["locked"]].upper() == "TRUE"
            if column_map["locked"] < len(row)
            else False
        )
        archived = (
            row[column_map["archived"]].upper() == "TRUE"
            if column_map["archived"] < len(row)
            else False
        )

        # Skip rows without a job_id (safety)
        if not job_id:
            continue

        # Detect duplicate job_ids (critical safety check)
        if job_id in job_index:
            raise RuntimeError(f"Duplicate job_id detected: {job_id}")

        job_index[job_id] = sheet_row_index
        jobs[job_id] = {
            "row_index": sheet_row_index,
            "applied": applied,
            "locked": locked,
            "archived": archived,
        }

    return job_index, jobs

def normalize_text(text):
    """
    Normalizes text for identity comparison.
    - lowercases
    - removes punctuation
    - collapses whitespace
    """
    if not text:
        return ""

    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)   # remove punctuation
    text = re.sub(r"\s+", " ", text)      # collapse whitespace
    return text.strip()


def normalize_company_name(company):
    """
    Normalizes company names by:
    - lowercasing
    - removing punctuation
    - removing common legal suffixes
    - collapsing whitespace
    """
    if not company:
        return ""

    company = company.lower()
    company = re.sub(r"[^\w\s]", "", company)

    # Remove common legal suffixes
    suffixes = {
        "inc", "incorporated",
        "llc", "ltd", "limited",
        "corp", "corporation",
        "co", "company"
    }

    words = company.split()
    words = [w for w in words if w not in suffixes]

    return " ".join(words).strip()


def generate_job_id(company, job_title, location):
    """
    Generates a deterministic job_id from identity fields.
    """

    norm_company = normalize_company_name(company)
    norm_title = normalize_text(job_title)
    norm_location = normalize_text(location)

    identity_string = f"{norm_company}|{norm_title}|{norm_location}"

    # Use SHA-256 for stable, deterministic hashing
    return hashlib.sha256(identity_string.encode("utf-8")).hexdigest()


def update_single_cell(
    service,
    spreadsheet_id,
    sheet_name,
    job_id,
    column_name,
    new_value,
    job_index,
    jobs,
    column_map,
):
    """
    Safely updates a single cell in the Jobs sheet.

    Enforces:
    - Column-level write permissions
    - Row-level locking
    - Primary-key targeting (job_id)
    """

    # --- Validate column ---
    if column_name in USER_OWNED_COLUMNS:
        raise RuntimeError(
            f"Agent is not allowed to write to user-owned column: {column_name}"
        )

    if column_name not in SYSTEM_WRITABLE_COLUMNS:
        raise RuntimeError(
            f"Column '{column_name}' is not writable by the system"
        )

    # --- Validate job exists ---
    if job_id not in job_index:
        raise RuntimeError(f"Unknown job_id: {job_id}")

    job = jobs[job_id]

    # --- Enforce locking rule ---
    if job["locked"] and column_name != "last_updated":
        raise RuntimeError(
            f"Job {job_id} is locked; cannot update '{column_name}'"
        )

    # --- Resolve row & column ---
    row_index = job_index[job_id]
    col_index = column_map[column_name]

    # Convert column index to A1 notation (e.g. 0 -> A, 1 -> B)
    col_letter = chr(ord("A") + col_index)
    range_name = f"{sheet_name}!{col_letter}{row_index}"

    # --- Perform update ---
    body = {
        "values": [[str(new_value)]]
    }

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="RAW",
        body=body,
    ).execute()


def get_sheet_id(service, spreadsheet_id, sheet_name):
    spreadsheet = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id
    ).execute()

    for sheet in spreadsheet["sheets"]:
        if sheet["properties"]["title"] == sheet_name:
            return sheet["properties"]["sheetId"]

    raise RuntimeError(f"Sheet '{sheet_name}' not found")


def insert_row_at_top(service, spreadsheet_id, sheet_id):
    """
    Inserts a new row directly below the header row.
    """

    body = {
        "requests": [
            {
                "insertDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": 1,  # 0-based, row 2 in UI
                        "endIndex": 2,
                    },
                    "inheritFromBefore": False,
                }
            }
        ]
    }

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=body,
    ).execute()



def append_new_job(
    service,
    spreadsheet_id,
    sheet_name,
    sheet_id,
    job_data,
    column_map,
):
    """
    Inserts a new job row at the TOP of the sheet (below headers).
    """

    # 1. Insert a new empty row at the top
    insert_row_at_top(service, spreadsheet_id, sheet_id)

    # 2. Build row data
    row_length = len(column_map)
    new_row = [""] * row_length

    def set_cell(column_name, value):
        if column_name not in column_map:
            return
        idx = column_map[column_name]
        new_row[idx] = str(value)

    # Identity + source fields
    set_cell("job_id", job_data["job_id"])
    set_cell("job_url", job_data["job_url"])
    set_cell("source", job_data["source"])
    set_cell("date_found", job_data["date_found"])
    set_cell("job_title", job_data["job_title"])
    set_cell("company", job_data["company"])
    set_cell("location", job_data["location"])
    set_cell("date_posted", job_data["date_posted"])

    # State initialization
    set_cell("applied", "FALSE")
    set_cell("locked", "FALSE")
    set_cell("archived", "FALSE")
    set_cell("last_updated", job_data["date_found"])

    # 3. Write into row 2
    range_name = f"{sheet_name}!A2"

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="RAW",
        body={"values": [new_row]},
    ).execute()


def process_raw_job(
    raw_job,
    service,
    spreadsheet_id,
    sheet_name,
    sheet_id,
    job_index,
    jobs,
    rows,
    column_map,
):
    """
    Processes ONE job safely:
    - appends if new
    - updates metadata if existing
    - respects locks and permissions
    """

    from datetime import datetime, timezone

    # ──────────────────────────────
    # 1. Generate deterministic ID
    # ──────────────────────────────
    job_id = generate_job_id(
        company=raw_job["company"],
        job_title=raw_job["job_title"],
        location=raw_job["location"],
    )

    now = datetime.now(timezone.utc).isoformat()

    # ──────────────────────────────
    # 2. NEW JOB → APPEND
    # ──────────────────────────────
    if job_id not in job_index:
        job_data = {
            "job_id": job_id,
            "job_url": raw_job["job_url"],
            "source": raw_job["source"],
            "date_found": now,
            "job_title": raw_job["job_title"],
            "company": raw_job["company"],
            "location": raw_job["location"],
            "date_posted": raw_job.get("date_posted", ""),
        }

        append_new_job(
            service=service,
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            sheet_id=sheet_id,
            job_data=job_data,
            column_map=column_map,
        )

        return "appended"

    # ──────────────────────────────
    # 3. EXISTING JOB
    # ──────────────────────────────
    state = jobs[job_id]

    # Locked = absolute stop
    if state["locked"]:
        return "locked"

    # Resolve existing row
    row_number = job_index[job_id]     # Sheet row (1-based)
    row_idx = row_number - 2            # rows[] is 0-based, excludes header
    existing_row = rows[row_idx]

    def get_existing(column):
        idx = column_map.get(column)
        if idx is None or idx >= len(existing_row):
            return ""
        return existing_row[idx]

    # ──────────────────────────────
    # 4. DIFF-CHECK SYSTEM FIELDS
    # ──────────────────────────────
    updates = {
        "job_url": raw_job["job_url"],
        "source": raw_job["source"],
        "date_posted": raw_job.get("date_posted", ""),
    }

    updated_anything = False

    for column_name, new_value in updates.items():
        old_value = get_existing(column_name)

        # Only write if value actually changed
        if str(old_value) != str(new_value):
            update_single_cell(
                service=service,
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                job_id=job_id,
                column_name=column_name,
                new_value=new_value,
                job_index=job_index,
                jobs=jobs,
                column_map=column_map,
            )
            updated_anything = True

    # ──────────────────────────────
    # 5. ALWAYS UPDATE last_updated
    # ──────────────────────────────
    update_single_cell(
        service=service,
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        job_id=job_id,
        column_name="last_updated",
        new_value=now,
        job_index=job_index,
        jobs=jobs,
        column_map=column_map,
    )

    return "updated" if updated_anything else "exists"


def refresh_jobs(
    raw_jobs,
    service,
    spreadsheet_id,
    sheet_name,
    sheet_id,
):
    """
    Refreshes the sheet against a list of raw jobs.
    Safe to run repeatedly (idempotent).
    """

    # Always start from fresh sheet state
    _, rows, column_map = read_jobs_sheet()
    job_index, jobs = build_job_index(rows, column_map)

    results = {
        "appended": 0,
        "updated": 0,
        "exists": 0,
        "locked": 0,
    }

    for raw_job in raw_jobs:
        result = process_raw_job(
            raw_job=raw_job,
            service=service,
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            sheet_id=sheet_id,
            job_index=job_index,
            jobs=jobs,
            rows=rows,
            column_map=column_map,
        )

        results[result] += 1

        # CRITICAL:
        # Sheet structure may have changed (top insert),
        # so we must re-read state after every mutation
        _, rows, column_map = read_jobs_sheet()
        job_index, jobs = build_job_index(rows, column_map)

    return results

