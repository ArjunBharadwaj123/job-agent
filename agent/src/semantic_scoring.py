"""
Scores jobs by semantic similarity between a resume and a job description,
using the Gemini embeddings API.

Degrades gracefully everywhere: missing resume file, missing API key,
empty description, or a failed embedding request all result in `None`
rather than an exception -- callers should fall back to the existing
keyword-based score in that case (see scoring.blend_scores).

NOTE: the older "text-embedding-004" model was retired by Google and now
404s; the current embedding model is "gemini-embedding-001" (verified
against the live ListModels endpoint). Google occasionally renames/
deprecates embedding models, so if embedding calls start 404ing again,
re-check with `GET .../v1beta/models` and update EMBEDDING_MODEL. Note
this model requires a billing-enabled project -- an unfunded key returns
429 "prepayment credits are depleted", which (like any failure here)
degrades to keyword-only scoring rather than crashing the run.
"""

import math
import os

import requests

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{EMBEDDING_MODEL}:embedContent"
)
DEFAULT_RESUME_PATH = "resume.txt"
REQUEST_TIMEOUT = 15


def load_resume(path: str = DEFAULT_RESUME_PATH) -> str:
    """
    Returns resume text, or "" if the file doesn't exist / can't be
    read. A missing resume is not an error -- it just means semantic
    scoring is unavailable for this run.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _embed_text(text: str, api_key: str):
    if not text or not api_key:
        return None

    try:
        response = requests.post(
            EMBEDDING_URL,
            params={"key": api_key},
            json={"content": {"parts": [{"text": text}]}},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Embedding request failed: {exc}")
        return None

    values = response.json().get("embedding", {}).get("values")
    return values or None


def _cosine_similarity(a, b):
    if not a or not b or len(a) != len(b):
        return None

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return None

    return dot / (norm_a * norm_b)


class SemanticScorer:
    """
    Embeds the resume once (lazily, on first use) and reuses it for
    every job scored in a run.
    """

    def __init__(
        self,
        resume_path: str = DEFAULT_RESUME_PATH,
        api_key: str = None,
        resume_text: str = None,
    ):
        self.api_key = api_key or os.environ.get(GEMINI_API_KEY_ENV)
        # Prefer resume text passed in directly (e.g. read from the Resume
        # sheet tab); fall back to the file only when none was provided.
        self.resume_text = resume_text if resume_text is not None else load_resume(resume_path)
        self._resume_embedding = None
        self._resume_embedding_attempted = False

    @property
    def available(self) -> bool:
        return bool(self.resume_text and self.api_key)

    def _get_resume_embedding(self):
        if not self._resume_embedding_attempted:
            self._resume_embedding_attempted = True
            if self.available:
                self._resume_embedding = _embed_text(self.resume_text, self.api_key)

        return self._resume_embedding

    def score(self, job_description: str):
        """
        Returns a similarity score in [0, 100], or None if semantic
        scoring isn't available for this job.
        """
        if not job_description:
            return None

        resume_embedding = self._get_resume_embedding()
        if resume_embedding is None:
            return None

        job_embedding = _embed_text(job_description, self.api_key)
        similarity = _cosine_similarity(resume_embedding, job_embedding)
        if similarity is None:
            return None

        similarity = max(-1.0, min(1.0, similarity))
        return round((similarity + 1) / 2 * 100)
