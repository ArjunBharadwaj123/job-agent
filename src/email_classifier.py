"""
Classify a job-application email into the dashboard's status vocabulary and
extract any assessment/interview link.

Primary backend is Groq (llama-3.3-70b-versatile); falls back to keyword rules
when GROQ_API_KEY is unset or the call fails. Both return the same shape:
    {status, confidence, reasoning, action_type, action_url}
status is one of: applied, pending, assessment, interview, rejected, accepted,
unknown. "unknown" means "not a status email" and should be skipped.
"""

import json
import os
import re
import time

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
# Groq is behind Cloudflare, which 1010-blocks default library user-agents.
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

VALID_STATUSES = {
    "applied", "pending", "assessment", "interview", "rejected", "accepted", "unknown",
}

# Domains that identify an action link and its type.
_ASSESSMENT_DOMAINS = ("hackerrank", "codesignal", "codility", "karat", "coderpad", "hackerearth", "testgorilla")
_INTERVIEW_DOMAINS = ("calendly", "greenhouse.io/scheduling", "goodtime", "modernloop", "hire.withgoogle", "cronofy", "x.ai")

_SYSTEM = """You classify a single job-application email for a candidate's tracker.
Return ONLY JSON with these keys:
- "status": one of ["applied","pending","assessment","interview","rejected","accepted","unknown"].
  Use the FURTHEST stage the email implies. "unknown" = not about an application's status.
- "confidence": 0.0-1.0.
- "reasoning": one short sentence.
- "action_type": "assessment" | "interview" | null (only if the email links to one).
- "action_url": the assessment/interview URL from the provided list, or null.
Guidance: rejection ("unfortunately", "not moving forward") -> rejected;
online assessment / coding challenge / OA -> assessment;
scheduling / availability / interview invite -> interview;
offer -> accepted; generic "we received your application" -> applied."""


def classify(email, job):
    if os.environ.get("GROQ_API_KEY"):
        result = _classify_groq(email, job)
        if result:
            return _finalize(result, email)
    return _finalize(classify_rules(email, job), email)


def _classify_groq(email, job):
    user = (
        f"Company: {job.get('company','')}\n"
        f"Role: {job.get('job_title','')}\n"
        f"Email subject: {email.get('subject','')}\n"
        f"Email from: {email.get('from','')}\n"
        f"Links in email: {email.get('urls', [])[:8]}\n\n"
        f"Email body:\n{email.get('body_text','')[:4000]}"
    )
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }
    headers = {
        "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
        "Content-Type": "application/json",
        "User-Agent": _UA,
    }
    # Retry on 429 (free-tier rate limit) with exponential backoff, honoring
    # Retry-After when present. Fall back to rules only after exhausting these.
    data = None
    for attempt in range(4):
        try:
            resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
            if resp.status_code == 429:
                wait = float(resp.headers.get("retry-after", 2 ** attempt))
                print(f"  Groq 429 — retrying in {wait:.0f}s")
                time.sleep(min(wait, 20))
                continue
            resp.raise_for_status()
            data = json.loads(resp.json()["choices"][0]["message"]["content"])
            break
        except (requests.RequestException, KeyError, ValueError) as exc:
            print(f"  Groq classify failed ({str(exc)[:60]}); using rules")
            return None
    if data is None:
        return None

    status = str(data.get("status", "unknown")).lower().strip()
    if status not in VALID_STATUSES:
        status = "unknown"
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "status": status,
        "confidence": max(0.0, min(1.0, confidence)),
        "reasoning": str(data.get("reasoning", "")).strip()[:300],
        "action_type": data.get("action_type"),
        "action_url": data.get("action_url"),
    }


# ----------------------------
# Keyword-rules fallback (fully local, no API)
# ----------------------------

_RULES = [
    ("rejected", 0.8, re.compile(r"unfortunately|regret to inform|not (be )?moving forward|will not be proceeding|decided not to|other candidates|no longer under consideration", re.I)),
    ("accepted", 0.85, re.compile(r"pleased to offer|offer of employment|offer letter|congratulations.*offer|extend an offer", re.I)),
    ("assessment", 0.8, re.compile(r"online assessment|coding (challenge|assessment)|hackerrank|codesignal|codility|take[- ]home|technical assessment|\bOA\b", re.I)),
    ("interview", 0.78, re.compile(r"schedule (a|your)|availability|interview|phone screen|calendly|book a time|meet with", re.I)),
    ("pending", 0.5, re.compile(r"under review|reviewing your application|has been received and", re.I)),
    ("applied", 0.4, re.compile(r"thank you for applying|we received your application|application (has been )?received", re.I)),
]


def classify_rules(email, job):
    text = f"{email.get('subject','')} {email.get('body_text','')}"
    for status, conf, pattern in _RULES:
        if pattern.search(text):
            return {"status": status, "confidence": conf, "reasoning": "matched keyword rule",
                    "action_type": None, "action_url": None}
    return {"status": "unknown", "confidence": 0.0, "reasoning": "no rule matched",
            "action_type": None, "action_url": None}


# ----------------------------
# Link resolution (domain heuristics override/repair the model's guess)
# ----------------------------

def _finalize(result, email):
    action_type, action_url = _resolve_link(email.get("urls", []))
    if action_url:
        result["action_type"] = action_type
        result["action_url"] = action_url
    elif result.get("action_url") and result.get("action_type") not in ("assessment", "interview"):
        # Model returned a url but no valid type; drop it.
        result["action_url"] = None
        result["action_type"] = None
    return result


def _resolve_link(urls):
    for url in urls:
        low = url.lower()
        if any(d in low for d in _ASSESSMENT_DOMAINS):
            return "assessment", url
    for url in urls:
        low = url.lower()
        if any(d in low for d in _INTERVIEW_DOMAINS):
            return "interview", url
    return None, None
