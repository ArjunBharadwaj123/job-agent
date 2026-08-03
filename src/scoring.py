"""
Shared scoring/classification logic used by all scrapers.

Extracted from scrapers/simplify_github.py so that new sources (e.g. the
Google Search scraper) score and classify jobs the same way instead of
re-implementing this logic and drifting out of sync.
"""

import re
from datetime import date

US_STATES = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
    "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
    "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
    "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
    "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
    "dc",
}

SWE_KEYWORDS = {
    "software", "engineer", "developer",
    "backend", "frontend", "full stack",
}

ML_KEYWORDS = {
    "machine learning", "ml", "ai",
    "data", "research",
}

# Positive signal: title/snippet explicitly reads as entry-level.
ENTRY_LEVEL_KEYWORDS = {
    "entry level", "entry-level", "junior", "associate",
    "new grad", "new graduate", "recent graduate", "graduate",
    "0-1 years", "0-2 years", "no experience required",
}

# Negative signal: presence of ANY of these disqualifies, regardless of
# positive matches (e.g. "Senior Associate" is not entry-level).
SENIOR_LEVEL_KEYWORDS = {
    "senior", "sr.", "sr ", "staff", "principal", "lead",
    "manager", "director", "head of",
    "5+ years", "6+ years", "7+ years", "8+ years", "10+ years",
}


def is_us_location(location: str) -> bool:
    """
    True if location is remote, or resolves to a recognizable US state
    (including the SimplifyJobs shorthand for NYC/SF).

    Uses a word-boundary regex for state codes so e.g. "Toronto, Canada"
    doesn't false-positive match the "ca" (California) code.
    """
    loc = location.lower()

    if "canada" in loc:
        return False

    if "remote" in loc:
        return True

    has_state = any(re.search(rf",\s*{s}\b", loc) for s in US_STATES)
    if not has_state and loc in ("nyc", "sf", "sfnyc"):
        has_state = True

    return has_state


def classify_role(title: str) -> str:
    t = title.lower()

    if "intern" in t:
        return "internship"
    if "new grad" in t or "graduate" in t:
        return "new_grad"
    return "other"


def is_entry_level(title: str, snippet: str = "") -> bool:
    """
    Entry-level if a positive keyword is present and no negative
    (seniority) keyword is present. Internships count as entry-level.
    """
    text = f"{title} {snippet}".lower()

    if any(kw in text for kw in SENIOR_LEVEL_KEYWORDS):
        return False

    if "intern" in text:
        return True

    return any(kw in text for kw in ENTRY_LEVEL_KEYWORDS)


# ---------------------------------------------------------------------------
# Strict new-grad / entry-level gate (used by the google_search pipeline).
#
# is_entry_level() above is lenient and, when fed a full job description,
# false-positives badly: generic words like "graduate"/"associate" appear in
# many mid/senior descriptions. This gate judges SENIORITY from the title
# only (titles are clean; descriptions are noise), recognizes level markers
# the old list missed (II/III/IV, "Level 3", "Sr", "3+ years"), and only
# rescues a plain-titled role when the description carries a *strong*
# new-grad phrase -- never on a bare "graduate"/"associate".
# ---------------------------------------------------------------------------

# Seniority markers in a TITLE -> not entry-level. Longest roman numerals
# first so "\biii\b" wins over "\bii\b".
_SENIOR_TITLE_RE = re.compile(
    r"\b(?:senior|sr\.?|staff|principal|lead|manager|director|head\s+of|"
    r"experienced|mid[-\s]?level|"
    r"iv|iii|ii|v|"                       # roman numerals II-V (levels)
    r"level\s*[2-9]|l[2-9]|"              # "Level 3" / "L4"
    r"[3-9]\+?\s*years?|1\d\+?\s*years?)\b",
    re.IGNORECASE,
)

# Positive entry signal in a TITLE.
_ENTRY_TITLE_RE = re.compile(
    r"\b(?:entry[-\s]?level|junior|jr\.?|new\s*grad(?:uate)?|recent\s+graduate|"
    r"associate|graduate|campus|early[-\s]?career|university\s+graduate|"
    r"college\s+graduate|apprentice|trainee|intern|rotational|"
    r"(?:engineer|developer|analyst)\s*i)\b",   # "... Engineer I" (level 1)
    re.IGNORECASE,
)

# Strong new-grad phrases that may rescue a plain-titled role from its
# DESCRIPTION. Deliberately excludes the bare words "graduate"/"associate"
# that caused the false positives.
_ENTRY_DESC_PHRASES = (
    "new grad", "new graduate", "recent graduate", "recent college graduate",
    "entry level", "entry-level", "early career", "early-career",
    "university graduate", "college graduate", "campus hire",
    "0-1 years", "0-2 years", "no experience required", "class of 20",
)


def has_senior_title(title: str) -> bool:
    """
    True if the TITLE carries a seniority marker (senior/staff/principal/
    lead/manager/II-V/level 2+/N+ years/...).

    A pure negative gate: unlike is_new_grad_or_entry() it does NOT require a
    positive entry signal. Meant for already-curated new-grad sources (e.g.
    the New-Grad-Positions repo), where the list itself vouches that roles are
    entry-level -- so "Software Engineer 1" should be kept -- but the odd
    senior title that slips in ("Senior Software Engineer 1") still needs
    dropping.
    """
    return bool(_SENIOR_TITLE_RE.search((title or "").lower()))


def is_new_grad_or_entry(title: str, description: str = "") -> bool:
    """
    True only for genuine new-grad / entry-level roles.

    - A seniority marker in the TITLE is disqualifying (checked first).
    - Else an entry signal in the TITLE qualifies.
    - Else a *strong* new-grad phrase in the DESCRIPTION rescues an
      otherwise-plain title (so a "Software Engineer" req that says
      "New Grad, Class of 2027" is kept, but a generic one is dropped).
    """
    t = (title or "").lower()

    if _SENIOR_TITLE_RE.search(t):
        return False

    if _ENTRY_TITLE_RE.search(t):
        return True

    d = (description or "").lower()
    return any(phrase in d for phrase in _ENTRY_DESC_PHRASES)


def compute_relevance_score(title: str, location: str) -> int:
    t = title.lower()
    score = 0

    for kw in SWE_KEYWORDS:
        if kw in t:
            score += 30

    for kw in ML_KEYWORDS:
        if kw in t:
            score += 15

    if "intern" in t:
        score += 20

    return max(min(score, 100), 0)


def compute_confidence(score: int, passed_filters: bool) -> float:
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


MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

SEASON_MONTHS = {
    "spring": 3,
    "summer": 6,
    "fall": 9,
    "autumn": 9,
    "winter": 12,
}

_START_KEYWORD_RE = re.compile(
    r"\b(?:start|starts|starting|begin|begins|beginning)\b", re.IGNORECASE
)
_MONTH_YEAR_RE = re.compile(
    r"(?P<month>" + "|".join(MONTH_NAMES.keys()) + r")\.?\s+(?P<year>20\d{2})",
    re.IGNORECASE,
)
_SEASON_YEAR_RE = re.compile(
    r"(?P<season>" + "|".join(SEASON_MONTHS.keys()) + r")\s+(?P<year>20\d{2})",
    re.IGNORECASE,
)
_START_DATE_SEARCH_WINDOW = 40


def extract_start_date(text: str):
    """
    Best-effort extraction of a job's start date from free text (title +
    description). Looks for a month+year or season+year mentioned shortly
    after a "start"/"begin" keyword (e.g. "Start Date: June 2027",
    "starting Summer 2027", "must start by May 2027").

    Returns a date (first of the identified month), or None if no
    start-date signal was found. None means "unknown," not "immediate" --
    plenty of legitimate postings just don't mention a start date.
    """
    if not text:
        return None

    for keyword_match in _START_KEYWORD_RE.finditer(text):
        window = text[keyword_match.end():keyword_match.end() + _START_DATE_SEARCH_WINDOW]

        month_year = _MONTH_YEAR_RE.search(window)
        if month_year:
            month = MONTH_NAMES[month_year.group("month").lower()]
            return date(int(month_year.group("year")), month, 1)

        season_year = _SEASON_YEAR_RE.search(window)
        if season_year:
            season = season_year.group("season").lower()
            return date(int(season_year.group("year")), SEASON_MONTHS[season], 1)

    return None


# Graduation / class-year phrasing, e.g. "Class of 2027", "2027 New Grad",
# "graduating in 2027", "University Graduate, 2027". Many new-grad postings
# signal their timing by the target grad year rather than a start date.
_GRAD_KEYWORD_RE = re.compile(
    r"\b(?:class\s+of|graduat\w*|new\s*grad\w*)\b", re.IGNORECASE
)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_GRAD_YEAR_LOOKBEHIND = 15
_GRAD_YEAR_LOOKAHEAD = 25

# Explicit "starts now" phrasing -> the role begins before any future grad
# date, so it's too early for someone graduating in 2027.
_IMMEDIATE_START_RE = re.compile(
    r"\b(?:start(?:s|ing)?\s+(?:immediately|asap)|immediate(?:ly)?\s+start|"
    r"start\s+date[:\s]+(?:asap|immediate\w*))\b",
    re.IGNORECASE,
)


def extract_grad_year(text: str):
    """
    Best-effort target graduation year from grad/class phrasing. Returns an
    int year (e.g. 2027) or None. Looks for a 20xx year adjacent to a
    graduation keyword ("class of 2027", "2027 new grad", "graduating 2027").
    """
    if not text:
        return None

    for keyword_match in _GRAD_KEYWORD_RE.finditer(text):
        start = max(0, keyword_match.start() - _GRAD_YEAR_LOOKBEHIND)
        window = text[start:keyword_match.end() + _GRAD_YEAR_LOOKAHEAD]
        year_match = _YEAR_RE.search(window)
        if year_match:
            return int(year_match.group(1))

    return None


def passes_start_date_filter(title: str, description: str, min_start_date) -> bool:
    """
    "Smart new-grad" start-date gate. Returns True to KEEP a job, False to
    drop it, given the earliest acceptable start date (a date).

    Precedence:
      1. Explicit start date in the text is authoritative: keep iff >= min.
      2. Else a graduation/class year is authoritative: keep iff that year
         >= min_start_date.year (so min May 2027 keeps "Class of 2027"+ and
         drops "Class of 2026").
      3. Else an explicit immediate-start signal ("ASAP") -> starts now,
         before min -> drop.
      4. Else the start date is genuinely unknown -> keep (lenient), so the
         many legit postings that simply don't state a date aren't discarded.
    """
    text = f"{title} {description}"

    start = extract_start_date(text)
    if start is not None:
        return start >= min_start_date

    grad_year = extract_grad_year(text)
    if grad_year is not None:
        return grad_year >= min_start_date.year

    if _IMMEDIATE_START_RE.search(text):
        return False

    return True


def blend_scores(keyword_score: int, semantic_score, semantic_weight: float = 0.6) -> int:
    """
    Combines a keyword-based relevance score with an optional semantic
    similarity score (0-100, or None if unavailable). Semantic scoring
    is weighted more heavily when present, since it reflects actual
    resume/description content rather than a handful of keyword hits --
    but when it's unavailable (no resume/API key configured, embedding
    call failed, empty description) this just returns keyword_score
    unchanged so the pipeline degrades gracefully.
    """
    if semantic_score is None:
        return keyword_score

    blended = semantic_weight * semantic_score + (1 - semantic_weight) * keyword_score
    return max(0, min(100, round(blended)))
