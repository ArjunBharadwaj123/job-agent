# matching/matcher.py

def normalize(text: str) -> str:
    return text.lower() if text else ""


def title_matches_preferences(title: str, preferences: dict) -> bool:
    title = title.lower()

    role_level_keywords = preferences.get("role_level_keywords", set())
    role_type_keywords = preferences.get("role_type_keywords", set())

    # Must match role level (e.g. intern, associate)
    if role_level_keywords:
        if not any(k in title for k in role_level_keywords):
            return False

    # Must match role type (e.g. software, backend)
    if role_type_keywords:
        if not any(k in title for k in role_type_keywords):
            return False

    return True


def filter_jobs(jobs: list[dict], preferences: dict) -> list[dict]:
    """
    Filters jobs based on user intent.
    """
    filtered = []

    for job in jobs:
        title = job.get("job_title", "")
        if title_matches_preferences(title, preferences):
            filtered.append(job)

    return filtered

