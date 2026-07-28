import os
import re
from datetime import datetime, timedelta, timezone

import requests

import scoring

SERPAPI_URL = "https://serpapi.com/search.json"

# SerpAPI's free tier is 100 searches/MONTH (unlike Google's own Custom
# Search API, which was 100/day). This only guards against one run
# blowing the entire month's quota in a single shot -- it does not track
# cumulative usage across runs/days, since that needs persistent state
# this project doesn't have. Size job_titles x locations with the
# monthly cap in mind, not a daily one.
QUERY_SAFETY_CAP = 100

REMOTE_RE = re.compile(r"\bremote\b", re.IGNORECASE)

# Google Jobs' "location" field sometimes has a "(+2 others)" suffix for
# multi-location postings -- strip it so location comparisons work.
_LOCATION_SUFFIX_RE = re.compile(r"\s*\(\+\d+\s+others?\)\s*$", re.IGNORECASE)

# detected_extensions.posted_at looks like "12 days ago" / "1 month ago".
_RELATIVE_DATE_RE = re.compile(r"(\d+)\s*(hour|day|week|month|year)s?\s*ago", re.IGNORECASE)
_RELATIVE_DATE_UNIT_DAYS = {"hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}


class GoogleSearchScraper:
    """
    Scrapes Google's "Jobs" search vertical (the structured job-card
    panel, not generic web search results) via SerpAPI's google_jobs
    engine. Unlike a plain web search, this returns clean structured
    fields directly -- company name, location, and a full job
    description -- so there's no need to guess at company/title/location
    by parsing a messy page-title string.
    """

    SOURCE_NAME = "google_search"

    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("SERPAPI_API_KEY")

    def run(self, settings: dict):
        self.settings = settings

        if not self.api_key:
            raise RuntimeError(
                "SERPAPI_API_KEY must be set (as an env var) to run the "
                "Google Search scraper."
            )

        queries = self._build_queries(settings)

        raw_jobs = []
        for i, (query_title, query_location, query) in enumerate(queries, start=1):
            print(f"[{i}/{len(queries)}] Searching: {query_title}, {query_location}")
            items = self._search(query)
            for item in items:
                candidate = self._parse_result(item, query_location)
                if not candidate:
                    continue
                if not self._passes_filters(candidate):
                    continue
                raw_jobs.append(self._build_raw_job(candidate))

        return raw_jobs

    # ----------------------------
    # Query construction
    # ----------------------------

    def _build_queries(self, settings):
        titles = settings.get("job_titles", [])
        locations = settings.get("locations", [])

        queries = []
        for title in titles:
            for location in locations:
                queries.append((title, location, f"{title}, {location}"))

        if len(queries) > QUERY_SAFETY_CAP:
            print(
                f"Warning: {len(queries)} queries requested but capped at "
                f"{QUERY_SAFETY_CAP} per run (SerpAPI's free tier is "
                f"100/MONTH, not /day -- size job_titles x locations "
                f"accordingly). Truncating."
            )
            queries = queries[:QUERY_SAFETY_CAP]

        return queries

    def _search(self, query):
        try:
            response = requests.get(
                SERPAPI_URL,
                params={
                    "engine": "google_jobs",
                    "q": query,
                    "api_key": self.api_key,
                },
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"Search failed for {query!r}: {exc}")
            return []

        data = response.json()
        if "error" in data:
            print(f"Search failed for {query!r}: {data['error']}")
            return []

        return data.get("jobs_results", [])

    # ----------------------------
    # Result parsing
    # ----------------------------

    def _parse_result(self, item, query_location):
        title = item.get("title") or item.get("job_title") or ""
        company = item.get("company_name", "").strip()
        location = self._clean_location(item.get("location", "")) or query_location
        link = item.get("source_link") or self._first_apply_link(item)
        description = item.get("description", "")
        detected = item.get("detected_extensions", {}) or {}

        if not title or not company or not link:
            return None

        return {
            "job_title": title,
            "company": company,
            "location": location,
            "job_url": link,
            "description": description,
            "date_posted": self._parse_relative_date(detected.get("posted_at", "")),
            "schedule_type": detected.get("schedule_type", ""),
        }

    def _clean_location(self, location):
        return _LOCATION_SUFFIX_RE.sub("", location or "").strip()

    def _first_apply_link(self, item):
        options = item.get("apply_options") or []
        if options:
            return options[0].get("link", "")
        return ""

    def _parse_relative_date(self, text):
        match = _RELATIVE_DATE_RE.search(text or "")
        if not match:
            return ""

        count = int(match.group(1))
        unit = match.group(2).lower()
        days = count * _RELATIVE_DATE_UNIT_DAYS.get(unit, 0)

        posted = datetime.now(timezone.utc) - timedelta(days=days)
        return posted.date().isoformat()

    # ----------------------------
    # Filtering + scoring
    # ----------------------------

    def _passes_filters(self, candidate):
        # NOTE: deliberately does NOT use settings["required_job_type"] or
        # settings["keywords"] -- those two are tuned for the GitHub/
        # SimplifyJobs internship pipeline ("must contain 'intern'", "must
        # contain one of these SWE keywords") and would fight against this
        # source's actual targeting, which already happens via job_titles
        # (what we search for) and entry_level_only (below).
        settings = self.settings
        location = candidate["location"].lower()
        description = candidate.get("description", "")

        # Only full-time roles -- drop internships/part-time/contract, and
        # drop postings where Google didn't detect a schedule type at all
        # rather than letting them through ambiguously.
        if candidate.get("schedule_type", "").strip().lower() != "full-time":
            return False

        if settings.get("entry_level_only") and not scoring.is_entry_level(
            candidate["job_title"], description
        ):
            return False

        if settings.get("us_only") and not scoring.is_us_location(location):
            return False

        if not settings.get("remote_allowed") and "remote" in location:
            return False

        return True

    def _build_raw_job(self, candidate):
        title = candidate["job_title"]
        location = candidate["location"]
        description = candidate.get("description", "")

        score = scoring.compute_relevance_score(title, location)
        if scoring.is_entry_level(title, description):
            score = min(score + 20, 100)

        return {
            "job_title": title,
            "company": candidate["company"],
            "location": location,
            "job_url": candidate["job_url"],
            "source": self.SOURCE_NAME,
            "date_posted": candidate.get("date_posted", ""),
            # Not a sheet column -- read by run_google_search_ingestion.py
            # for semantic scoring / start-date filtering without a
            # separate page fetch, since Google Jobs already gives us the
            # full description. sheet_reader ignores unrecognized keys.
            "description": description,
            "relevance_score": score,
            "role_type": scoring.classify_role(title),
            "confidence": scoring.compute_confidence(score, True),
        }
