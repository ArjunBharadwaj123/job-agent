"""
Pure normalization + identity helpers, shared across the pipeline.

These functions used to live in the Google-Sheets modules (`sheet_reader.py`,
`settings_reader.py`). The Sheets backend has been fully replaced by Turso, so
the helpers that survived — deterministic job IDs, company/text normalization,
and typed settings parsing — were extracted here with no external dependencies.
"""

import hashlib
import re
from datetime import datetime


# ----------------------------
# Text / identity normalization
# ----------------------------

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


# ----------------------------
# Settings normalization
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

    # Numeric settings. Parsed defensively: an empty or non-numeric value
    # (e.g. a blank field saved from the dashboard Settings tab) falls back to
    # the default instead of raising ValueError and failing the whole run.
    settings["max_days_back"] = _int_setting(raw_settings, "max_days_back", 0)
    settings["max_jobs"] = _int_setting(raw_settings, "max_jobs", 50)
    # Bounds how much of the unscored backlog each run drains. Defaults to 25.
    settings["max_backfill"] = _int_setting(raw_settings, "max_backfill", 25)

    # US-only flag (bool)
    settings["us_only"] = raw_settings.get(
        "us_only", "false"
    ).strip().lower() == "true"

    # Remote allowed flag (bool)
    settings["remote_allowed"] = raw_settings.get(
        "remote_allowed", "false"
    ).strip().lower() == "true"

    return settings


def _int_setting(raw_settings, key, default):
    """Parse an int setting, falling back to default on empty/non-numeric."""
    value = str(raw_settings.get(key, "")).strip()
    if not value:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
