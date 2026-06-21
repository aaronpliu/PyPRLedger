"""ID obfuscation utility using hashids.

Transforms numeric database primary keys into opaque, non-sequential,
URL-safe short strings for user-facing display. Full reversibility
is maintained without any database storage.

Usage:
    >>> from src.utils.id_obfuscator import format_public_id, parse_public_id

    # Encode a review ID for display
    public_id = format_public_id("review", 42)    # "rev_kM8xP31R"

    # Decode back to entity type and real ID
    entity, real_id = parse_public_id("rev_kM8xP31R")  # ("review", 42)
"""

from src.core.config import settings


try:
    from hashids import Hashids
except ImportError:
    Hashids = None  # type: ignore


# Entity type registry: maps entity type key → prefix
# Add new entities here when extending obfuscation to other types
ENTITY_PREFIXES: dict[str, str] = {
    "review": "rev",
    "score": "sco",
    "user": "usr",
    "rule": "rule",
    "raw": "raw",
}

# Reverse mapping: prefix → entity type key
_PREFIX_TO_ENTITY: dict[str, str] = {v: k for k, v in ENTITY_PREFIXES.items()}


def _get_hashids() -> "Hashids":
    """Get the hashids instance with configured salt."""
    if Hashids is None:
        raise ImportError("hashids package is not installed. Run: pip install hashids")
    return Hashids(salt=settings.ID_OBFUSCATOR_SALT, min_length=10)


def encode(real_id: int) -> str:
    """Encode a numeric ID into an opaque string.

    Args:
        real_id: The database primary key to encode.

    Returns:
        An opaque alphanumeric string (e.g., 'kM8xP31R').

    Raises:
        ValueError: If real_id is negative.
    """
    if real_id < 0:
        raise ValueError(f"Cannot encode negative ID: {real_id}")
    return _get_hashids().encode(real_id)


def decode(encoded: str) -> int | None:
    """Decode an opaque string back to the original numeric ID.

    Args:
        encoded: The opaque string to decode.

    Returns:
        The original integer ID, or None if the string is invalid.
    """
    if not encoded:
        return None
    result = _get_hashids().decode(encoded)
    return result[0] if result else None


def format_public_id(entity_type: str, real_id: int) -> str:
    """Create a prefixed public ID string for display.

    The format is: {prefix}_{encoded_id}
    Example: 'rev_kM8xP31R' for a review with ID 42.

    Args:
        entity_type: The entity type key (e.g., 'review', 'score', 'user', 'rule').
        real_id: The database primary key to encode.

    Returns:
        A prefixed public ID string.

    Raises:
        ValueError: If entity_type is unknown or real_id is negative.
    """
    prefix = ENTITY_PREFIXES.get(entity_type)
    if not prefix:
        valid = ", ".join(ENTITY_PREFIXES)
        raise ValueError(f"Unknown entity type '{entity_type}'. Valid types: {valid}")
    encoded = encode(real_id)
    return f"{prefix}_{encoded}"


def parse_public_id(public_id: str) -> tuple[str, int] | None:
    """Parse a prefixed public ID string back to entity type and real ID.

    Args:
        public_id: The prefixed public ID string (e.g., 'rev_kM8xP31R').

    Returns:
        A tuple of (entity_type, real_id), or None if the string is invalid.
    """
    if not public_id or "_" not in public_id:
        return None

    prefix, encoded = public_id.split("_", 1)
    entity_type = _PREFIX_TO_ENTITY.get(prefix)
    if not entity_type or not encoded:
        return None

    real_id = decode(encoded)
    if real_id is None:
        return None

    return entity_type, real_id
