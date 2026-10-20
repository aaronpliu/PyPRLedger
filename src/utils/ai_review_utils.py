"""Utility functions for AI review identifier generation and extraction"""

import hashlib


# The severities an AI review reports for the issues it found, most severe first.
# Stored on reviews inside ai_suggestions["issues"][*]["severity"], so anything that
# filters or matches on severity reads them from here.
ISSUE_SEVERITIES = ("critical", "high", "medium", "low")


def extract_issue_severities(ai_suggestions: dict | None) -> list[str]:
    """The severities of the issues an AI review reported, in the order they appear.

    A review that found nothing - or was never analysed - has no severities, which is
    what a rule matching on severity reads as "does not match".

    Args:
        ai_suggestions: The AI review payload, shaped ``{"issues": [{"severity": ...}]}``

    Returns:
        Lower-case severity strings, duplicates included as reported
    """
    if not isinstance(ai_suggestions, dict):
        return []

    issues = ai_suggestions.get("issues")
    if not isinstance(issues, list):
        return []

    severities: list[str] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        severity = str(issue.get("severity") or "").strip().lower()
        if severity:
            severities.append(severity)
    return severities


def generate_ai_review_id(
    project_key: str,
    repository_slug: str,
    pull_request_commit_id: str | None,
) -> str:
    """
    Generate unique AI review identifier per PR.

    The ID is deterministic based on PR identifiers, ensuring the same PR
    always gets the same AI review ID even when re-reviewed.

    Args:
        project_key: Project key (e.g., 'ECOM')
        repository_slug: Repository slug (e.g., 'frontend-store')
        pull_request_commit_id: Commit ID for this PR state

    Returns:
        Unique AI review identifier in format: ai_rev_<16-char-hash>

    Example:
        >>> generate_ai_review_id('ECOM', 'frontend-store', 'abc123')
        'ai_rev_a1b2c3d4e5f67890'
    """
    # Create content string for hashing
    # Use __NO_COMMIT__ as placeholder if commit_id is None
    commit_id = pull_request_commit_id or "__NO_COMMIT__"
    content = f"{project_key}:{repository_slug}:__PR_LEVEL__:{commit_id}"

    # Generate SHA-256 hash and take first 16 characters for readability
    hash_value = hashlib.sha256(content.encode()).hexdigest()[:16]

    return f"ai_rev_{hash_value}"
