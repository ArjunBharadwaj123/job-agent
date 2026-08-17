import logging
import re

import pandas as pd
from jobspy import scrape_jobs

import scoring


# JobSpy logs each board on its own logger named "JobSpy:<Site>" (with
# propagate=False), so per-board failures never bubble up as exceptions --
# a blocked board just returns zero rows. To tell "blocked" apart from
# "genuinely no results" we attach a handler to each of these loggers and
# capture their ERROR records (403/429/400/etc.).
_SITE_LOGGER_NAMES = {
    "google": "Google",
    "linkedin": "LinkedIn",
    "indeed": "Indeed",
    "glassdoor": "Glassdoor",
    "zip_recruiter": "ZipRecruiter",
}

# Pretty names for logs / notifications.
SITE_DISPLAY = {
    "google": "Google",
    "linkedin": "LinkedIn",
    "indeed": "Indeed",
    "glassdoor": "Glassdoor",
    "zip_recruiter": "ZipRecruiter",
}

_STATUS_CODE_RE = re.compile(r"\b(4\d\d|5\d\d)\b")

# Trailing country tokens (after lowercasing + punctuation removal) that
# different boards append to locations. Stripped so the dedup identity
# matches across boards. See JobSpyScraper._normalize_location.
_COUNTRY_TOKENS = {
    "us",
    "usa",
    "united states",
    "united states of america",
}


def _norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


# Normalized site key lookups: the DataFrame's `site` column uses values like
# "zip_recruiter"; the loggers use "ZipRecruiter". Both normalize to the same
# key so we can match either back to our config key.
_SITE_BY_NORM = {_norm(k): k for k in _SITE_LOGGER_NAMES}
_LOGGER_SHORT_TO_KEY = {_norm(v): k for k, v in _SITE_LOGGER_NAMES.items()}


def _short_reason(messages):
    """Extract a concise blocked-reason (e.g. 'HTTP 403') from log messages."""
    for msg in reversed(messages):
        match = _STATUS_CODE_RE.search(msg)
        if match:
            return f"HTTP {match.group(1)}"
    if messages:
        return messages[-1].split(" with response")[0][:60]
    return ""


class _BoardStatusHandler(logging.Handler):
    """Captures ERROR records from JobSpy per-site loggers, keyed by site."""

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.errors = {}

    def emit(self, record):
        if record.levelno < logging.ERROR:
            return
        short = record.name.split(":")[-1]
        key = _LOGGER_SHORT_TO_KEY.get(_norm(short))
        if key:
            self.errors.setdefault(key, []).append(record.getMessage())


def _attach_board_handler(handler):
    attached = []
    for short in _SITE_LOGGER_NAMES.values():
        logger = logging.getLogger(f"JobSpy:{short}")
        logger.addHandler(handler)
        attached.append(logger)
    return attached


def _detach_board_handler(handler, attached):
    for logger in attached:
        logger.removeHandler(handler)


class JobSpyScraper:
    """
    Scrapes multiple job boards (Google Jobs, LinkedIn, Indeed, Glassdoor,
    ZipRecruiter) via the `python-jobspy` library, which returns one
    unified pandas DataFrame per query. This replaces the SerpAPI-based
    GoogleSearchScraper as the primary source.

    Like the other scrapers in this package it exposes `run(settings) ->
    list[dict]`, emitting the same raw-job dict schema so everything
    downstream (dedup, semantic scoring, sheet upload, notify) is
    unchanged. Scoring reuses `scoring.py` exactly as google_search.py does.
    """

    SOURCE_NAME = "jobspy"

    # Boards to pull from. Kept in code for now; can be promoted to the
    # Settings tab later without touching the rest of the pipeline.
    SITES = ["google", "linkedin", "indeed", "glassdoor", "zip_recruiter"]

    # Per site, per (title x location) query. The overall run is still hard-
    # capped downstream by settings["max_jobs"] in the runner.
    RESULTS_PER_QUERY = 25

    # Circuit breaker: after a board hard-fails (block/error + zero rows) this
    # many queries in a row, drop it for the rest of the run instead of
    # re-requesting it every query. Boards like Glassdoor/ZipRecruiter that are
    # WAF-blocked otherwise get hammered once per (title x location) combo,
    # which dominates run time (JobSpy retries/backs off on each 403/400).
    FAIL_LIMIT = 2

    # Per-board outcome of the last run(): {site: {collected, status, reason}}.
    # status is one of "collected" / "blocked" / "none". Read by the runner
    # and forwarded to the ntfy notification.
    board_status: dict = {}

    def run(self, settings: dict) -> list[dict]:
        self.settings = settings

        titles = settings.get("job_titles", [])
        locations = settings.get("locations", [])

        # Count what each board actually returned (pre-filter) and capture any
        # block/error logs, so we can report collected-vs-blocked per board.
        collected = {site: 0 for site in self.SITES}
        handler = _BoardStatusHandler()
        attached = _attach_board_handler(handler)

        # Circuit-breaker state: which boards are still worth querying.
        active_sites = list(self.SITES)
        consecutive_fail = {site: 0 for site in self.SITES}

        raw_jobs = []
        queries = [(t, loc) for t in titles for loc in locations]
        try:
            for i, (title, location) in enumerate(queries, start=1):
                if not active_sites:
                    print("All boards disabled (blocked); stopping scrape early.")
                    break

                print(f"[{i}/{len(queries)}] Scraping: {title}, {location}")

                # Snapshot error counts so we can tell which boards failed
                # *this* query (handler.errors accumulates across the run).
                err_before = {
                    s: len(handler.errors.get(s, [])) for s in active_sites
                }

                df = self._scrape(title, location, active_sites)
                self._tally_collected(df, collected)

                counts_this = self._counts_by_site(df)
                self._update_circuit_breaker(
                    active_sites, consecutive_fail, counts_this,
                    handler.errors, err_before,
                )

                for _, row in df.iterrows():
                    candidate = self._parse_row(row, location)
                    if not candidate:
                        continue
                    if not self._passes_filters(candidate):
                        continue
                    raw_jobs.append(self._build_raw_job(candidate))
        finally:
            _detach_board_handler(handler, attached)

        self.board_status = self._summarize_boards(collected, handler.errors)
        self._print_board_status()
        return raw_jobs

    def _counts_by_site(self, df):
        counts = {}
        if df is None or df.empty or "site" not in df.columns:
            return counts
        for value, count in df["site"].value_counts().items():
            key = _SITE_BY_NORM.get(_norm(value))
            if key:
                counts[key] = int(count)
        return counts

    def _update_circuit_breaker(
        self, active_sites, consecutive_fail, counts_this, errors, err_before
    ):
        for site in list(active_sites):
            errored = len(errors.get(site, [])) > err_before.get(site, 0)
            if counts_this.get(site, 0) > 0:
                consecutive_fail[site] = 0
            elif errored:
                consecutive_fail[site] += 1
                if consecutive_fail[site] >= self.FAIL_LIMIT:
                    active_sites.remove(site)
                    print(
                        f"  Disabling {SITE_DISPLAY.get(site, site)} for the "
                        f"rest of this run after {self.FAIL_LIMIT} blocked "
                        f"attempts"
                    )

    # ----------------------------
    # Per-board status tracking
    # ----------------------------

    def _tally_collected(self, df, collected):
        if df is None or df.empty or "site" not in df.columns:
            return
        for value, count in df["site"].value_counts().items():
            key = _SITE_BY_NORM.get(_norm(value))
            if key in collected:
                collected[key] += int(count)

    def _summarize_boards(self, collected, errors):
        status = {}
        for site in self.SITES:
            count = collected.get(site, 0)
            errs = errors.get(site, [])
            if count > 0:
                state = "collected"
            elif errs:
                state = "blocked"
            else:
                state = "none"
            status[site] = {
                "collected": count,
                "status": state,
                "reason": _short_reason(errs) if state == "blocked" else "",
            }
        return status

    def _print_board_status(self):
        print("Board status:")
        for site, info in self.board_status.items():
            name = SITE_DISPLAY.get(site, site)
            if info["status"] == "collected":
                print(f"  {name}: collected {info['collected']}")
            elif info["status"] == "blocked":
                reason = f" ({info['reason']})" if info["reason"] else ""
                print(f"  {name}: BLOCKED{reason}")
            else:
                print(f"  {name}: no results")

    # ----------------------------
    # Scraping
    # ----------------------------

    def _scrape(self, title, location, sites):
        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=title,
                google_search_term=f"{title} jobs near {location}",
                location=location,
                results_wanted=self.RESULTS_PER_QUERY,
                job_type="fulltime",
                # Indeed/Glassdoor require a country; US-centric either way.
                country_indeed="usa",
                # Deliberately DON'T fetch LinkedIn descriptions here: it costs
                # one extra rate-limited request per posting, and we scrape far
                # more jobs than we keep (results are capped to max_jobs
                # downstream). The runner fetches descriptions lazily via
                # description_fetcher for only the capped set, so we pay that
                # cost ~max_jobs times instead of thousands.
                linkedin_fetch_description=False,
                description_format="markdown",
                hours_old=self._hours_old(),
                verbose=0,
            )
        except Exception as exc:
            print(f"Scrape failed for {title!r}, {location!r}: {exc}")
            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()
        return df

    def _hours_old(self):
        # google_search deliberately ignores max_days_back; mirror that by
        # only applying a recency window when explicitly configured.
        max_days_back = self.settings.get("max_days_back")
        if not max_days_back:
            return None
        try:
            return int(max_days_back) * 24
        except (TypeError, ValueError):
            return None

    # ----------------------------
    # Result parsing
    # ----------------------------

    def _parse_row(self, row, query_location):
        title = self._clean(row.get("title"))
        company = self._clean(row.get("company"))
        location = self._normalize_location(
            self._clean(row.get("location")) or query_location
        )
        # Prefer the direct employer link when JobSpy resolved one.
        link = self._clean(row.get("job_url_direct")) or self._clean(
            row.get("job_url")
        )
        description = self._clean(row.get("description"))
        date_posted = self._parse_date(row.get("date_posted"))
        is_remote = bool(row.get("is_remote")) if pd.notna(
            row.get("is_remote")
        ) else False
        # The actual board JobSpy scraped this row from (linkedin, indeed,
        # glassdoor, zip_recruiter, google) -- used as the `source`.
        site_raw = self._clean(row.get("site"))
        source = _SITE_BY_NORM.get(_norm(site_raw), site_raw) or self.SOURCE_NAME

        if not title or not company or not link:
            return None

        return {
            "job_title": title,
            "company": company,
            "location": location,
            "job_url": link,
            "description": description,
            "date_posted": date_posted,
            "is_remote": is_remote,
            "source": source,
        }

    @staticmethod
    def _clean(value):
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_location(location):
        """
        Canonicalize a location so the same real job doesn't dedupe as two
        rows across boards. Different boards tack on a trailing country token
        ("New York, NY, US" vs "New York, NY"); we strip trailing
        country-only (or empty) comma segments so the identity triple
        (company, title, location) matches. Genuinely different cities/states
        are preserved, and a location that is ONLY a country (e.g. nationwide
        "United States") is kept rather than emptied.
        """
        if not location:
            return ""

        parts = [p.strip() for p in location.split(",")]
        while len(parts) > 1:
            tail = re.sub(r"[^\w\s]", "", parts[-1].lower())
            tail = re.sub(r"\s+", " ", tail).strip()
            if tail == "" or tail in _COUNTRY_TOKENS:
                parts.pop()
            else:
                break
        return ", ".join(parts).strip()

    @staticmethod
    def _parse_date(value):
        if value is None or pd.isna(value):
            return ""
        # JobSpy usually gives a datetime.date/Timestamp; sometimes a string.
        try:
            return pd.Timestamp(value).date().isoformat()
        except (ValueError, TypeError):
            return str(value)[:10]

    # ----------------------------
    # Filtering + scoring
    # ----------------------------

    def _passes_filters(self, candidate):
        # Mirrors GoogleSearchScraper._passes_filters, minus the strict
        # schedule_type == "full-time" gate: JobSpy frequently leaves
        # job_type empty, and we already pass job_type="fulltime" to
        # scrape_jobs, so hard-dropping empties here would kill most
        # legitimate results. Deliberate, documented deviation.
        settings = self.settings
        location = candidate["location"].lower()
        description = candidate.get("description", "")

        if settings.get("entry_level_only") and not scoring.is_new_grad_or_entry(
            candidate["job_title"], description
        ):
            return False

        if settings.get("us_only") and not scoring.is_us_location(location):
            return False

        if not settings.get("remote_allowed") and (
            candidate.get("is_remote") or "remote" in location
        ):
            return False

        return True

    def _build_raw_job(self, candidate):
        title = candidate["job_title"]
        location = candidate["location"]
        description = candidate.get("description", "")

        score = scoring.compute_relevance_score(title, location)
        if scoring.is_new_grad_or_entry(title, description):
            score = min(score + 20, 100)

        return {
            "job_title": title,
            "company": candidate["company"],
            "location": location,
            "job_url": candidate["job_url"],
            # The board this posting actually came from (e.g. "linkedin",
            # "indeed"), not a generic "jobspy" tag.
            "source": candidate.get("source") or self.SOURCE_NAME,
            "date_posted": candidate.get("date_posted", ""),
            # Not a sheet column -- read by the runner for semantic scoring /
            # start-date filtering without a separate page fetch, since
            # JobSpy already gives us the full description. sheet_reader
            # ignores unrecognized keys.
            "description": description,
            "relevance_score": score,
            "role_type": scoring.classify_role(title),
            "confidence": scoring.compute_confidence(score, True),
        }
