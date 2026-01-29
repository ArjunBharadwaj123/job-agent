import requests
import re
from bs4 import BeautifulSoup


class GreenhouseScraper:
    """
    Scrapes job listings from Greenhouse-hosted job boards.
    Handles:
    - 1-indexed pagination
    - repeated jobs across pages
    - multiple Greenhouse domains
    """

    LEGACY_DOMAIN_COMPANIES = {
        "airbnb",  # uses boards.greenhouse.io
    }

    def __init__(self, company_slug: str):
        self.company_slug = company_slug.lower()

        # Choose correct base domain
        if self.company_slug in self.LEGACY_DOMAIN_COMPANIES:
            self.base_url = f"https://boards.greenhouse.io/{self.company_slug}"
            self.job_domain = "https://boards.greenhouse.io"
        else:
            self.base_url = f"https://job-boards.greenhouse.io/{self.company_slug}"
            self.job_domain = "https://job-boards.greenhouse.io"

    def fetch_jobs(self) -> list[dict]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        all_jobs = []
        seen_job_ids = set()

        page = 1
        MAX_PAGES = 25  # safety cap

        while True:
            # Greenhouse pagination is 1-indexed
            if page == 1:
                url = self.base_url
            else:
                url = f"{self.base_url}?page={page}"

            print(f"Fetching {url}")

            try:
                response = requests.get(url, headers=headers, timeout=20)
            except requests.RequestException as e:
                print(f"⚠️ Request failed: {e}")
                break

            if response.status_code != 200:
                print(f"⚠️ Status {response.status_code}, stopping")
                break

            soup = BeautifulSoup(response.text, "html.parser")

            # Collect all job links on the page
            job_links = soup.select('a[href*="/jobs/"]')

            page_new_jobs = 0

            for link in job_links:
                href = link.get("href", "").strip()
                if not href:
                    continue

                # Extract numeric job ID (Greenhouse invariant)
                last_segment = href.rstrip("/").split("/")[-1]
                match = re.search(r"(\d+)", last_segment)
                if not match:
                    continue

                job_id = match.group(1)

                # Skip jobs we've already seen
                if job_id in seen_job_ids:
                    continue

                seen_job_ids.add(job_id)
                page_new_jobs += 1

                # Normalize job URL
                if href.startswith("http"):
                    job_url = href
                else:
                    job_url = f"{self.job_domain}{href}"

                job_title = link.get_text(strip=True)

                all_jobs.append({
                    "job_title": job_title,
                    "job_url": job_url,
                    "location": "",
                    "company": self.company_slug,
                    "source": "greenhouse",
                    "date_posted": "",
                })

            print(f"Page {page}: {page_new_jobs} new jobs")

            # ✅ CORRECT STOP CONDITION
            if page_new_jobs == 0:
                print("No new jobs found — stopping pagination")
                break

            page += 1

            # Safety cap
            if page > MAX_PAGES:
                print("⚠️ Max page limit reached, stopping")
                break

        return all_jobs
