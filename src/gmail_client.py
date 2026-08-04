"""
Read-only Gmail access for the daily status scan. Builds a Gmail API client
from a stored refresh token and returns recent messages as plain dicts
(subject, sender, body text, extracted URLs).
"""

import base64
import os
import re
from html import unescape

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_URI = "https://oauth2.googleapis.com/token"

_URL_RE = re.compile(r"https?://[^\s<>\"')]+")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_ADDR_RE = re.compile(r"@([A-Za-z0-9.-]+)")


def get_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        client_id=os.environ["GMAIL_CLIENT_ID"],
        client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def recent_messages(days=3, max_results=120, service=None):
    """Return recent inbox messages as parsed dicts, newest first."""
    service = service or get_service()
    query = f"newer_than:{days}d -in:chats"
    ids = []
    page_token = None
    while len(ids) < max_results:
        resp = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=min(100, max_results - len(ids)),
                pageToken=page_token,
            )
            .execute()
        )
        ids.extend(m["id"] for m in resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    messages = []
    for mid in ids[:max_results]:
        full = (
            service.users()
            .messages()
            .get(userId="me", id=mid, format="full")
            .execute()
        )
        messages.append(_parse_message(full))
    return messages


def thread_url(thread_id):
    return f"https://mail.google.com/mail/u/0/#inbox/{thread_id}"


def _parse_message(msg):
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    sender = headers.get("from", "")
    domain_match = _ADDR_RE.search(sender)
    body_text = _extract_body(msg.get("payload", {}))
    urls = _URL_RE.findall(body_text)
    return {
        "id": msg["id"],
        "thread_id": msg.get("threadId", ""),
        "subject": headers.get("subject", ""),
        "from": sender,
        "from_domain": (domain_match.group(1).lower() if domain_match else ""),
        "date": headers.get("date", ""),
        "snippet": unescape(msg.get("snippet", "")),
        "body_text": body_text,
        "urls": _dedupe(urls),
    }


def _extract_body(payload):
    """Walk MIME parts; prefer text/plain, fall back to stripped text/html."""
    plain, html = _collect_parts(payload)
    text = plain or _strip_html(html)
    text = _WS_RE.sub(" ", unescape(text)).strip()
    return text[:8000]


def _collect_parts(part, plain="", html=""):
    mime = part.get("mimeType", "")
    body = part.get("body", {})
    data = body.get("data")
    if data:
        decoded = base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", "ignore")
        if mime == "text/plain":
            plain += decoded
        elif mime == "text/html":
            html += decoded
    for sub in part.get("parts", []) or []:
        plain, html = _collect_parts(sub, plain, html)
    return plain, html


def _strip_html(html):
    html = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html, flags=re.I)
    return _TAG_RE.sub(" ", html)


def _dedupe(seq):
    seen = set()
    out = []
    for x in seq:
        x = x.rstrip(".,);]")
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
