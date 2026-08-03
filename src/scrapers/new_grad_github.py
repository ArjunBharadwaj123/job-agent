"""
Scraper for the SimplifyJobs / Coder Quad New-Grad-Positions repo:
https://github.com/SimplifyJobs/New-Grad-Positions

Serves as a resilient fallback to the Google Search source: it needs no API
keys (just an HTTP GET of the README), so the daily run still produces jobs
even when SerpAPI/Gemini are down or return nothing.

Only the two categories the user cares about are ingested -- Software
Engineering and Data Science, AI & Machine Learning -- and only the ACTIVE
roles. Each category section in the README is a first "active" HTML table
followed by a "<details>🗃️ Inactive roles" block containing a second table of
expired roles; we truncate each section at that marker so inactive roles are
never picked up.

Shares scoring/classification with every other source via scoring.py. Its
filtering mirrors GoogleSearchScraper (us_only / remote_allowed + a negative
seniority gate) rather than the internship-era simplify_github filters --
required_job_type / keywords / max_days_back are intentionally NOT applied, as
they're tuned for internships and would drop new-grad roles (see
_passes_filters).
"""

import re
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

import scoring


class NewGradGitHubScraper:
    SOURCE_NAME = "new_grad_github"

    RAW_URL = (
        "https://raw.githubusercontent.com/"
        "SimplifyJobs/New-Grad-Positions/dev/README.md"
    )

    # Section headers (## ...) to ingest, matched case-insensitively on a
    # distinctive substring of the heading text.
    TARGET_SECTIONS = (
        "software engineering",
        "data science, ai & machine learning",
    )

    # Marker that begins the per-section "Inactive roles" details block. Text
    # before it is the active table; text from here on is dropped.
    INACTIVE_MARKER = "Inactive roles"

    def run(self, settings: dict):
        self.settings = settings
        markdown = self._fetch_markdown()
        rows = self._parse_active_rows(markdown)

        raw_jobs = []
        for row in rows:
            if not self._passes_filters(row):
                print(f"Filtered out: {row['company']} - {row['role']} ({row['location']}) - Age: {row['age']}")
                continue

            raw_jobs.append(self._build_raw_job(row))

        return raw_jobs

    def _fetch_markdown(self):
        response = requests.get(self.RAW_URL, timeout=20)
        response.raise_for_status()
        return response.text

    # ------------------------------------------------------------------
    # Section-scoped, active-only parsing
    # ------------------------------------------------------------------
    def _parse_active_rows(self, markdown: str):
        """
        Returns the active-role rows from the target sections only.

        Splits the README into `## ...` sections, keeps the ones whose heading
        matches TARGET_SECTIONS, truncates each at the "Inactive roles" marker,
        and parses the (single) active table within each.
        """
        rows = []
        for chunk in self._target_section_chunks(markdown):
            rows.extend(self._parse_table(chunk))
        return rows

    def _target_section_chunks(self, markdown: str):
        """
        Yields the active-table markdown for each target `## ` section.
        """
        # Split so each piece starts with its "## " heading line.
        parts = re.split(r"(?m)^(?=## )", markdown)

        for part in parts:
            header = part.splitlines()[0] if part else ""
            header_lc = header.lower()

            if not header_lc.startswith("## "):
                continue

            if not any(target in header_lc for target in self.TARGET_SECTIONS):
                continue

            # Drop everything from the Inactive-roles block onward.
            marker_idx = part.find(self.INACTIVE_MARKER)
            if marker_idx != -1:
                part = part[:marker_idx]

            yield part

    def _parse_table(self, markdown_chunk: str):
        soup = BeautifulSoup(markdown_chunk, "html.parser")

        tables = soup.find_all("table")
        if not tables:
            return []

        # The first (and, after truncation, only active) table in the section.
        table = tables[0]

        rows = []

        tbody = table.find("tbody")
        if not tbody:
            return rows

        current_company = None

        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue

            raw_company = self._clean_company(tds[0].get_text(strip=True))

            if raw_company == "↳" or not raw_company:
                company = current_company
            else:
                company = raw_company
                current_company = raw_company

            if not company:
                continue

            rows.append({
                "company": company,
                "role": tds[1].get_text(strip=True),
                "location": self._parse_location(tds[2]),
                "apply": tds[3].find("a")["href"] if tds[3].find("a") else "",
                "age": tds[4].get_text(strip=True),
            })

        return rows

    def _clean_company(self, text: str) -> str:
        """
        Strips the decorative emoji prefix (e.g. "🔥 Palantir" -> "Palantir")
        the repo uses to flag hot roles, while preserving the "↳" continuation
        marker so the caller can inherit the company above.
        """
        text = (text or "").strip()
        if text == "↳":
            return text
        # Remove any leading non-alphanumeric decorations (emoji + spaces).
        return re.sub(r"^[^\w(]+", "", text).strip()

    def _parse_location(self, td) -> str:
        """
        Location cells come in three shapes:
          - plain text: "London, UK"
          - a few locations inline, "<br>"-separated: "Concord, MA<br>Tewksbury, MA"
          - many locations in a "<details><summary><strong>N locations</strong>
            </summary>loc<br>loc...</details>" block.

        In every case we return the first concrete location for a clean value
        (multi-location roles still filter correctly on it, and the full list
        would only clutter the sheet). A "\n" separator is used so "<br>"
        boundaries survive get_text() instead of collapsing into one string.
        """
        details = td.find("details")
        if details:
            summary = details.find("summary")
            summary_text = summary.get_text(strip=True) if summary else ""
            source = details
        else:
            summary_text = ""
            source = td

        locations = [
            line.strip()
            for line in source.get_text("\n").split("\n")
            if line.strip() and line.strip() != summary_text
        ]
        return locations[0] if locations else td.get_text(strip=True)

    # ------------------------------------------------------------------
    # Shared scoring / classification (delegates to scoring.py)
    # ------------------------------------------------------------------
    def _classify_role(self, title: str) -> str:
        return scoring.classify_role(title)

    def _compute_relevance_score(self, title: str, location: str) -> int:
        return scoring.compute_relevance_score(title, location)

    def _compute_confidence(self, score: int, passed_filters: bool) -> float:
        return scoring.compute_confidence(score, passed_filters)

    def _compute_date_posted(self, age_str: str) -> str:
        if not age_str:
            return ""

        match = re.search(r"(\d+)", age_str.lower())
        if not match:
            return ""

        days_ago = int(match.group(1))
        posted_date = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return posted_date.date().isoformat()

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------
    def _passes_filters(self, row: dict) -> bool:
        """
        Mirrors GoogleSearchScraper._passes_filters, NOT simplify_github's.

        It deliberately does NOT apply settings["required_job_type"] or
        settings["keywords"]: those are legacy internship-pipeline knobs
        ("title must contain 'intern'", "title must contain a SWE keyword")
        that would wrongly drop new-grad full-time roles like "Software
        Engineer 1" or "Data Engineer 1". This source's category targeting is
        already done by only parsing the SWE + AI/ML sections. max_days_back is
        likewise skipped -- the repo lists newest-first and the max_jobs cap in
        the runner keeps only the freshest roles.
        """
        settings = self.settings
        title = row.get("role", "")
        location = row.get("location", "").lower()

        # Seniority gate (negative only, honoring entry_level_only). The repo
        # is curated new-grad, so trust its positive signal -- keep "Software
        # Engineer 1" -- but drop the odd senior title ("Senior Software
        # Engineer 1") that slips in.
        if settings.get("entry_level_only") and scoring.has_senior_title(title):
            return False

        # US-only filter
        if settings.get("us_only"):
            if "canada" in location:
                return False
            if not scoring.is_us_location(location):
                return False

        # Remote allowed
        if not settings.get("remote_allowed") and "remote" in location:
            return False

        return True

    def _build_raw_job(self, row: dict):
        title = row.get("role", "")
        location = row.get("location", "")

        score = self._compute_relevance_score(title, location)
        passed_filters = True  # already filtered earlier

        return {
            "job_title": title,
            "company": row.get("company", ""),
            "location": location,
            "job_url": row.get("apply", ""),
            "source": self.SOURCE_NAME,
            "date_posted": self._compute_date_posted(row.get("age", "")),
            "relevance_score": score,
            "role_type": self._classify_role(title),
            "confidence": self._compute_confidence(score, passed_filters),
        }
