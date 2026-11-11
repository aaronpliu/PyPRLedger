"""Shared helpers for repository-scoped visibility filtering."""

from __future__ import annotations

import hashlib

from sqlalchemy import and_, false, or_

from src.core.exceptions import ForbiddenException


RepositoryPair = tuple[str, str]


def repository_pair_condition(
    project_key_col, repository_slug_col, pairs: set[RepositoryPair] | None
):
    """SQL condition restricting rows to granted (project, repository) pairs.

    ``None`` means unrestricted (internal callers); an empty set means no access.
    """
    if pairs is None:
        return None
    if not pairs:
        return false()
    return or_(
        *[
            and_(project_key_col == project_key, repository_slug_col == repository_slug)
            for project_key, repository_slug in sorted(pairs)
        ]
    )


def allowed_project_keys(pairs: set[RepositoryPair] | None) -> set[str] | None:
    if pairs is None:
        return None
    return {project_key for project_key, _ in pairs}


def ensure_pair_granted(
    access: set[RepositoryPair] | None,
    project_key: str | None,
    repository_slug: str | None = None,
) -> None:
    """Raise ForbiddenException unless the caller holds a grant for the pair.

    ``None`` access means unrestricted (internal callers).
    """
    if access is None or project_key is None:
        return
    if project_key not in allowed_project_keys(access):
        raise ForbiddenException(message="No access to this project")
    if repository_slug and (project_key, repository_slug) not in access:
        raise ForbiddenException(message="No access to this repository")


def access_scope(values) -> str:
    """Stable, short cache-key fragment describing a user's grant set."""
    if values is None:
        return "all"
    if not values:
        return "none"
    raw = "|".join(
        "/".join(value) if isinstance(value, tuple) else str(value) for value in sorted(values)
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
