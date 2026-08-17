"""
Fetches the full text of a job posting page.

Google search snippets are only ~160 characters -- too short for a
meaningful semantic comparison against a resume. This module fetches the
actual posting page and pulls out the description, preferring structured
schema.org JobPosting JSON-LD (which most ATS platforms embed) over raw
page text, since the structured version is cleaner and often also carries
a reliable datePosted.
"""

import json
import re

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; JobAgentBot/1.0; +personal job tracker)"
FETCH_TIMEOUT = 10
MAX_DESCRIPTION_CHARS = 6000


def fetch_job_description(url: str) -> dict:
    """
    Returns {"description": str, "date_posted": str}.

    Both fields are "" on any failure -- network error, non-HTML
    response, unparseable page. This runs against arbitrary third-party
    sites that can't be trusted to respond reliably, so failures are
    treated as "no signal available," not raised as errors.
    """
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=FETCH_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        return {"description": "", "date_posted": ""}

    if "html" not in response.headers.get("Content-Type", ""):
        return {"description": "", "date_posted": ""}

    soup = BeautifulSoup(response.text, "html.parser")

    structured = _extract_job_posting_jsonld(soup)
    if structured["description"]:
        return structured

    return {
        "description": _extract_fallback_text(soup),
        "date_posted": structured["date_posted"],
    }


def _extract_job_posting_jsonld(soup) -> dict:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (TypeError, ValueError):
            continue

        for node in _flatten_jsonld(data):
            if _is_job_posting(node):
                description = _strip_html(node.get("description", ""))
                return {
                    "description": description[:MAX_DESCRIPTION_CHARS],
                    "date_posted": node.get("datePosted") or "",
                }

    return {"description": "", "date_posted": ""}


def _flatten_jsonld(data):
    if isinstance(data, list):
        for item in data:
            yield from _flatten_jsonld(item)
    elif isinstance(data, dict):
        if "@graph" in data:
            yield from _flatten_jsonld(data["@graph"])
        yield data


def _is_job_posting(node: dict) -> bool:
    node_type = node.get("@type", "")
    if isinstance(node_type, list):
        return "JobPosting" in node_type
    return node_type == "JobPosting"


def _strip_html(html_text: str) -> str:
    text = BeautifulSoup(html_text, "html.parser").get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def _extract_fallback_text(soup) -> str:
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()

    text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
    return text[:MAX_DESCRIPTION_CHARS]
