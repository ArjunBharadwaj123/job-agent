"""
Scraper for Jobright's public "landing" jobs feed:
https://jobright.ai/swan/recommend/landing/jobs

Like the SimplifyJobs New-Grad-Positions scraper this is a keyless fallback
source: it needs no API keys or login -- just an HTTP GET of a public JSON
endpoint -- so the daily run keeps producing jobs even when the JobSpy boards
are WAF-blocked. The endpoint returns a rolling window of the ~20 most recently
posted roles across all categories; it ignores query params, so we poll it a
few times and dedupe by jobId to accumulate a few more than a single call
yields (the feed shifts as new roles land).

The JSON is rich (title, company, location, work model, seniority, salary,
posted time, and a summary), so scoring can use the structured seniority /
years-of-experience signals directly rather than inferring everything from the
title. Scoring/classification is shared with every other source via scoring.py.
"""

import time
from datetime import datetime

import requests

import scoring


class JobRightScraper:
    SOURCE_NAME = "jobright"

    URL = "https://jobright.ai/swan/recommend/landing/jobs"

    # Cloudflare in front of jobright.ai blocks default library user-agents.
    _UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    )

    # The feed returns ~20 roles and shifts slowly between calls (empirically
    # ~18/20 overlap). Poll a few times to gather a few more unique roles, but
    # stop early once a poll adds nothing new so we don't hammer it for nothing.
    MAX_POLLS = 5
    POLL_PAUSE_SECONDS = 1.0

    # jobSeniority values that disqualify a role under entry_level_only.
    _SENIOR_SENIORITY = {"senior level", "director", "executive"}

    def run(self, settings: dict) -> list[dict]:
        self.settings = settings
        rows = self._fetch_rows()

        raw_jobs = []
        for row in rows:
            if not self._passes_filters(row):
                print(
                    f"Filtered out: {row['company']} - {row['job_title']} "
                    f"({row['location']}) - {row['seniority']}"
                )
                continue
            raw_jobs.append(self._build_raw_job(row))

        return raw_jobs

    # ------------------------------------------------------------------
    # Fetch + parse
    # ------------------------------------------------------------------
    def _fetch_rows(self) -> list[dict]:
        """Poll the feed, dedupe by jobId, and return parsed rows."""
        headers = {"User-Agent": self._UA, "Accept": "application/json"}
        seen = set()
        rows = []

        for poll in range(self.MAX_POLLS):
            try:
                resp = requests.get(self.URL, headers=headers, timeout=20)
                resp.raise_for_status()
                payload = resp.json()
            except (requests.RequestException, ValueError) as exc:
                print(f"Jobright fetch failed ({str(exc)[:80]})")
                break

            if not payload.get("success"):
                print(f"Jobright returned error: {payload.get('errorMsg')}")
                break

            new_this_poll = 0
            for item in payload.get("result", {}).get("jobList", []):
                row = self._parse_item(item)
                if not row or row["job_id"] in seen:
                    continue
                seen.add(row["job_id"])
                rows.append(row)
                new_this_poll += 1

            # Stop as soon as a poll adds nothing new (feed hasn't turned over).
            if poll > 0 and new_this_poll == 0:
                break
            if poll < self.MAX_POLLS - 1:
                time.sleep(self.POLL_PAUSE_SECONDS)

        print(f"Jobright: collected {len(rows)} unique roles")
        return rows

    def _parse_item(self, item: dict):
        job = item.get("jobResult") or {}
        company = item.get("companyResult") or {}

        job_id = (job.get("jobId") or "").strip()
        title = (job.get("jobTitle") or "").strip()
        company_name = (company.get("companyName") or "").strip()
        # Prefer the single-string location; fall back to the first of the list.
        location = (job.get("jobLocation") or "").strip()
        if not location and job.get("jobLocations"):
            location = str(job["jobLocations"][0]).strip()
        # applyLink and url are the same jobright detail page; either is fine.
        link = (job.get("applyLink") or job.get("url") or "").strip()

        if not job_id or not title or not company_name or not link:
            return None

        return {
            "job_id": job_id,
            "job_title": title,
            "company": company_name,
            "location": location,
            "job_url": link,
            "description": (job.get("jobSummary") or "").strip(),
            "date_posted": self._parse_date(job.get("publishTime")),
            "is_remote": bool(job.get("isRemote"))
            or (job.get("workModel") or "").strip().lower() == "remote",
            "seniority": (job.get("jobSeniority") or "").strip(),
            "min_years": self._parse_int(job.get("minYearsOfExperience")),
        }

    @staticmethod
    def _parse_date(value) -> str:
        """publishTime is 'YYYY-MM-DD HH:MM:SS'; keep the date part."""
        if not value:
            return ""
        text = str(value).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text[:19], fmt).date().isoformat()
            except ValueError:
                continue
        return text[:10]

    @staticmethod
    def _parse_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------
    def _passes_filters(self, row: dict) -> bool:
        """
        Mirrors NewGradGitHubScraper._passes_filters (us_only / remote_allowed +
        a negative seniority gate), but unlike that curated new-grad list the
        jobright feed carries roles at every level, so entry_level_only leans on
        the endpoint's structured seniority / years-of-experience signals in
        addition to the title heuristic.
        """
        settings = self.settings
        title = row["job_title"]
        location = row["location"].lower()

        if settings.get("entry_level_only") and self._is_senior(row):
            return False

        if settings.get("us_only"):
            if "canada" in location:
                return False
            if not scoring.is_us_location(location):
                return False

        if not settings.get("remote_allowed") and (
            row["is_remote"] or "remote" in location
        ):
            return False

        return True

    def _is_senior(self, row: dict) -> bool:
        if scoring.has_senior_title(row["job_title"]):
            return True
        if row["seniority"].lower() in self._SENIOR_SENIORITY:
            return True
        min_years = row["min_years"]
        return min_years is not None and min_years >= 3

    # ------------------------------------------------------------------
    # Shared scoring / classification (delegates to scoring.py)
    # ------------------------------------------------------------------
    def _build_raw_job(self, row: dict) -> dict:
        title = row["job_title"]
        location = row["location"]
        description = row["description"]

        score = scoring.compute_relevance_score(title, location)
        if scoring.is_new_grad_or_entry(title, description):
            score = min(score + 20, 100)

        return {
            "job_title": title,
            "company": row["company"],
            "location": location,
            "job_url": row["job_url"],
            "source": self.SOURCE_NAME,
            "date_posted": row["date_posted"],
            # Not a persisted column -- read by the runner for optional semantic
            # scoring, then dropped before upsert (see run_jobright_ingestion).
            "description": description,
            "relevance_score": score,
            "role_type": scoring.classify_role(title),
            "confidence": scoring.compute_confidence(score, True),
        }
