import requests
import re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

class SimplifyGitHubScraper:
    SOURCE_NAME = "simplify_github"

    RAW_URL = (
        "https://raw.githubusercontent.com/"
        "SimplifyJobs/Summer2026-Internships/dev/README.md"
    )

    def run(self, settings: dict):
        self.settings = settings
        markdown = self._fetch_markdown()
        rows = self._parse_table(markdown)

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

    def _parse_table(self, markdown: str):
        soup = BeautifulSoup(markdown, "html.parser")

        # Find all tables
        tables = soup.find_all("table")

        if not tables:
            return []

        # We want the Software Engineering Internship table
        # Assumption: first table under that section
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

            raw_company = tds[0].get_text(strip=True)

            if raw_company == "↳":
                company = current_company
            else:
                company = raw_company
                current_company = raw_company

            if not company:
                continue

            rows.append({
                "company": company,
                "role": tds[1].get_text(strip=True),
                "location": tds[2].get_text(strip=True),
                "apply": tds[3].find("a")["href"] if tds[3].find("a") else "",
                "age": tds[4].get_text(strip=True),
            })

        return rows


    def _classify_role(self, title: str) -> str:
        t = title.lower()

        if "intern" in t:
            return "internship"
        if "new grad" in t or "graduate" in t:
            return "new_grad"
        return "other"

    def _compute_relevance_score(self, title: str, location: str) -> int:
        t = title.lower()
        loc = location.lower()
        score = 0

        # Core SWE keywords
        swe_keywords = {
            "software", "engineer", "developer",
            "backend", "frontend", "full stack"
        }

        ml_keywords = {
            "machine learning", "ml", "ai",
            "data", "research"
        }

        for kw in swe_keywords:
            if kw in t:
                score += 30

        for kw in ml_keywords:
            if kw in t:
                score += 15

        if "intern" in t:
            score += 20

        # ──────────────────────────────
        # LOCATION PENALTIES
        # ──────────────────────────────
        us_states = {
            "al","ak","az","ar","ca","co","ct","de","fl","ga",
            "hi","id","il","in","ia","ks","ky","la","me","md",
            "ma","mi","mn","ms","mo","mt","ne","nv","nh","nj",
            "nm","ny","nc","nd","oh","ok","or","pa","ri","sc",
            "sd","tn","tx","ut","vt","va","wa","wv","wi","wy"
        }

        is_remote = "remote" in loc
        is_us = any(f", {s}" in loc for s in us_states)

        if not is_remote and not is_us:
            score -= 25   # soft penalty for non-US

        return max(min(score, 100), 0)


    def _compute_confidence(self, score: int, passed_filters: bool) -> float:
        """
        Confidence reflects certainty AFTER filtering.
        """

        if not passed_filters:
            return 0.2  # weak confidence

        if score >= 85:
            return 0.95
        if score >= 70:
            return 0.85
        if score >= 50:
            return 0.7
        if score >= 30:
            return 0.5

        return 0.3



    def _compute_date_posted(self, age_str: str) -> str:
        if not age_str:
            return ""

        match = re.search(r"(\d+)", age_str.lower())
        if not match:
            return ""

        days_ago = int(match.group(1))
        posted_date = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return posted_date.date().isoformat()

    def _passes_filters(self, row: dict) -> bool:
        title = row.get("role", "").lower()
        location = row.get("location", "").lower()
        age_str = row.get("age", "")


        if "mo" in age_str:
            return False

        settings = self.settings

        # ──────────────────────────────
        # 1. Required job type (MANDATORY)
        # ──────────────────────────────
        required_types = settings.get("required_job_type", [])

        if required_types:
            if not any(rt in title for rt in required_types):
                return False

        # ──────────────────────────────
        # 2. Keywords (at least one must match)
        # ──────────────────────────────
        keywords = settings.get("keywords", [])
        if keywords:
            if not any(kw in title for kw in keywords):
                return False

        # ──────────────────────────────
        # 3. Max days back
        # ──────────────────────────────
        match = re.search(r"(\d+)", age_str)
        if match:
            days_ago = int(match.group(1))
            if days_ago > settings.get("max_days_back", 999):
                return False

        # ──────────────────────────────
        # 4. US-only filter
        # ──────────────────────────────
        if settings.get("us_only"):

            if "canada" in location:
                return False

            us_states = {
                "al","ak","az","ar","ca","co","ct","de","fl","ga",
                "hi","id","il","in","ia","ks","ky","la","me","md",
                "ma","mi","mn","ms","mo","mt","ne","nv","nh","nj",
                "nm","ny","nc","nd","oh","ok","or","pa","ri","sc",
                "sd","tn","tx","ut","vt","va","wa","wv","wi","wy",
                "dc"
            }

            is_remote = "remote" in location
            has_state = any(f", {s}" in location for s in us_states)

            if not has_state and (location == "nyc" or location == "sf"):
                has_state = True

            if not is_remote and not has_state:
                return False

        # ──────────────────────────────
        # 5. Remote allowed
        # ──────────────────────────────
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

