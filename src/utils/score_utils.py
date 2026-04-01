from src.core.score_config import get_score_description as get_auto_description


def normalize_source_filename(source_filename: str | None) -> str | None:
    """
    Normalize source filename for consistent storage and querying

    - Empty string -> None (PR-level)
    - Whitespace only -> None (PR-level)
    - Valid path -> stripped path

    Returns:
        Normalized filename or None for PR-level scoring
    """
    if not source_filename or not source_filename.strip():
        return None
    return source_filename.strip()


def get_score_description(score: float, custom_description: str | None = None) -> str | None:
    """
    Get score description with fallback logic

    Args:
        score: The score value
        custom_description: Optional custom description provided by user

    Returns:
        Custom description if provided, otherwise auto-generated from mapping
    """
    if custom_description and custom_description.strip():
        return custom_description.strip()

    return get_auto_description(score)
