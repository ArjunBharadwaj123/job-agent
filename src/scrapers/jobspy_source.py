import pandas as pd
from jobspy import scrape_jobs

import scoring


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

    def run(self, settings: dict) -> list[dict]:
        self.settings = settings

        titles = settings.get("job_titles", [])
        locations = settings.get("locations", [])

        raw_jobs = []
        queries = [(t, loc) for t in titles for loc in locations]
        for i, (title, location) in enumerate(queries, start=1):
            print(f"[{i}/{len(queries)}] Scraping: {title}, {location}")
            df = self._scrape(title, location)
            for _, row in df.iterrows():
                candidate = self._parse_row(row, location)
                if not candidate:
                    continue
                if not self._passes_filters(candidate):
                    continue
                raw_jobs.append(self._build_raw_job(candidate))

        return raw_jobs

    # ----------------------------
    # Scraping
    # ----------------------------

    def _scrape(self, title, location):
        try:
            df = scrape_jobs(
                site_name=self.SITES,
                search_term=title,
                google_search_term=f"{title} jobs near {location}",
                location=location,
                results_wanted=self.RESULTS_PER_QUERY,
                job_type="fulltime",
                # Indeed/Glassdoor require a country; US-centric either way.
                country_indeed="usa",
                # LinkedIn omits descriptions unless we fetch each posting.
                # We need them for semantic scoring downstream.
                linkedin_fetch_description=True,
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
        location = self._clean(row.get("location")) or query_location
        # Prefer the direct employer link when JobSpy resolved one.
        link = self._clean(row.get("job_url_direct")) or self._clean(
            row.get("job_url")
        )
        description = self._clean(row.get("description"))
        date_posted = self._parse_date(row.get("date_posted"))
        is_remote = bool(row.get("is_remote")) if pd.notna(
            row.get("is_remote")
        ) else False

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
        }

    @staticmethod
    def _clean(value):
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            return ""
        return str(value).strip()

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
            "source": self.SOURCE_NAME,
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
