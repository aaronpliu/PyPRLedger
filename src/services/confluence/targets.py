"""Where the release pages of each repository are written.

An instance holds several projects with several repositories each, and releases
are published per repository, so one space for the whole instance cannot be the
answer. A target is resolved in three tiers, and each field falls back on its
own:

    space_key        repository -> project -> instance default
    parent_page_id   repository -> project -> instance default
    enabled          repository -> project -> instance default

Falling back field by field is what makes the usual arrangement expressible: a
space per project, said once, and a page per repository, said per repository.
Resolved as a whole, the space would have to be repeated on every repository.

What is stored is one JSON setting rather than a table, because this is
configuration read whole and written whole - the same shape the banners of the
reviews page use.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.system_setting import SystemSetting
from src.utils.log import get_logger


logger = get_logger(__name__)

SETTING_KEY = "confluence_targets"
SETTING_DESCRIPTION = "Confluence publishing targets, per project and per repository"

# Bounds, so a hand-edited row stays a configuration rather than a payload.
MAX_TARGETS = 200
MAX_KEY_LENGTH = 128
MAX_SPACE_KEY_LENGTH = 64
MAX_PAGE_ID_LENGTH = 32

# Where a resolved value came from, as the settings page reports it.
INSTANCE_SOURCE = "instance"
PROJECT_SOURCE = "project"
REPOSITORY_SOURCE = "repository"


@dataclass(frozen=True)
class Resolution:
    """The target one repository publishes to, and where each part came from."""

    space_key: str
    parent_page_id: str
    enabled: bool
    space_source: str
    parent_source: str
    enabled_source: str
    project_target: bool
    repository_target: bool

    @property
    def has_space(self) -> bool:
        """Whether there is a space to write into at all."""
        return bool(self.space_key)

    @property
    def configured(self) -> bool:
        """Whether either level says anything about this repository."""
        return self.project_target or self.repository_target

    def as_dict(self) -> dict[str, Any]:
        """The resolution as the settings page reads it."""
        return {
            "space_key": self.space_key,
            "parent_page_id": self.parent_page_id,
            "enabled": self.enabled,
            "space_source": self.space_source,
            "parent_source": self.parent_source,
            "enabled_source": self.enabled_source,
            "configured": self.configured,
        }


def empty_targets() -> dict[str, list[dict[str, Any]]]:
    """A configuration that says nothing anywhere."""
    return {"projects": [], "repositories": []}


def label(project_key: str, repository_slug: str) -> str:
    """How one repository is named in a message."""
    return f"{project_key}/{repository_slug}"


def _coerced_flag(value: object) -> bool:
    """Read a boolean that may arrive as the string the settings table stores."""
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def _normalize_entry(raw: object, *, with_repository: bool) -> dict[str, Any]:
    """Validate one target and bound every field of it.

    A field that is left empty means "not decided here" rather than "empty", which
    is exactly what lets the space be set on the project and the parent page on
    the repository.
    """
    if not isinstance(raw, dict):
        raise ValueError("each target must be an object")

    project_key = str(raw.get("project_key") or "").strip()
    if not project_key:
        raise ValueError("a target needs a project key")
    if len(project_key) > MAX_KEY_LENGTH:
        raise ValueError(f"a project key is longer than {MAX_KEY_LENGTH} characters")

    repository_slug = ""
    if with_repository:
        repository_slug = str(raw.get("repository_slug") or "").strip()
        if not repository_slug:
            raise ValueError("a repository target needs a repository slug")
        if len(repository_slug) > MAX_KEY_LENGTH:
            raise ValueError(f"a repository slug is longer than {MAX_KEY_LENGTH} characters")

    space_key = str(raw.get("space_key") or "").strip()
    if len(space_key) > MAX_SPACE_KEY_LENGTH:
        raise ValueError(f"a space key is longer than {MAX_SPACE_KEY_LENGTH} characters")
    if any(char.isspace() for char in space_key):
        raise ValueError("a space key cannot contain spaces")

    parent_page_id = str(raw.get("parent_page_id") or "").strip()
    if parent_page_id:
        if not parent_page_id.isdigit():
            raise ValueError("a parent page id is a number")
        if len(parent_page_id) > MAX_PAGE_ID_LENGTH:
            raise ValueError(f"a parent page id is longer than {MAX_PAGE_ID_LENGTH} digits")

    # Absent and false are not the same here: absent leaves the decision to the
    # level above, false means this repository does not publish.
    raw_enabled = raw.get("enabled")
    if raw_enabled is None or (isinstance(raw_enabled, str) and not raw_enabled.strip()):
        enabled: bool | None = None
    else:
        enabled = _coerced_flag(raw_enabled)

    if not space_key and not parent_page_id and enabled is None:
        raise ValueError(
            "a target must set a space key, a parent page id, or switch the repository off"
        )

    entry: dict[str, Any] = {"project_key": project_key}
    if with_repository:
        entry["repository_slug"] = repository_slug
    entry["space_key"] = space_key
    entry["parent_page_id"] = parent_page_id
    entry["enabled"] = enabled

    return entry


def _normalize_list(raw: object, *, key: str, with_repository: bool) -> list[dict[str, Any]]:
    """Validate one of the two lists, rejecting a level that is listed twice."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{key} must be a list")
    if len(raw) > MAX_TARGETS:
        raise ValueError(f"at most {MAX_TARGETS} {key} are supported")

    entries = [_normalize_entry(item, with_repository=with_repository) for item in raw]

    seen: set[tuple[str, ...]] = set()
    for entry in entries:
        identity = (
            (entry["project_key"], entry["repository_slug"])
            if with_repository
            else (entry["project_key"],)
        )
        if identity in seen:
            raise ValueError(f"{'/'.join(identity)} is listed more than once")
        seen.add(identity)

    return entries


def normalize_targets(raw: object) -> dict[str, list[dict[str, Any]]]:
    """Validate a whole configuration, as the settings endpoint receives it.

    Both lists are replaced together, so a write is the configuration from then
    on rather than a merge with what was there.
    """
    if not isinstance(raw, dict):
        raise ValueError("the targets must be an object")
    if "projects" not in raw and "repositories" not in raw:
        raise ValueError("projects or repositories is required")

    return {
        "projects": _normalize_list(raw.get("projects"), key="projects", with_repository=False),
        "repositories": _normalize_list(
            raw.get("repositories"), key="repositories", with_repository=True
        ),
    }


def _tolerant_list(raw: object, *, with_repository: bool) -> list[dict[str, Any]]:
    """Read one list, leaving out whatever cannot be used.

    The write path has already validated, so anything unusable here was put there
    by hand: dropping the one entry and keeping the rest beats failing a release
    over it.
    """
    if not isinstance(raw, list):
        return []

    entries: list[dict[str, Any]] = []
    for item in raw[:MAX_TARGETS]:
        try:
            entries.append(_normalize_entry(item, with_repository=with_repository))
        except ValueError as exc:
            logger.warning("Skipping an unusable Confluence target: %s", exc)

    return entries


def parse_stored_targets(value: str) -> dict[str, list[dict[str, Any]]]:
    """Read the stored configuration, or empty ones when it was never written.

    An unreadable row is reported and treated as absent: publishing has to keep
    working either way, and the settings page is where it gets put right.
    """
    if not value or not value.strip():
        return empty_targets()

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        logger.warning("Confluence targets are not valid JSON; treating them as unset")
        return empty_targets()

    if not isinstance(parsed, dict):
        logger.warning("Confluence targets are not an object; treating them as unset")
        return empty_targets()

    return {
        "projects": _tolerant_list(parsed.get("projects"), with_repository=False),
        "repositories": _tolerant_list(parsed.get("repositories"), with_repository=True),
    }


def _project_entry(
    config: dict[str, list[dict[str, Any]]], project_key: str
) -> dict[str, Any] | None:
    """The project-level target for one project, when there is one."""
    for entry in config.get("projects", []):
        if entry.get("project_key") == project_key:
            return entry
    return None


def _repository_entry(
    config: dict[str, list[dict[str, Any]]], project_key: str, repository_slug: str
) -> dict[str, Any] | None:
    """The repository-level target for one repository, when there is one."""
    for entry in config.get("repositories", []):
        if (
            entry.get("project_key") == project_key
            and entry.get("repository_slug") == repository_slug
        ):
            return entry
    return None


def _field(
    repository: dict[str, Any] | None,
    project: dict[str, Any] | None,
    key: str,
    default: str,
) -> tuple[str, str]:
    """The first level that decides a field, and which level that was."""
    for entry, source in ((repository, REPOSITORY_SOURCE), (project, PROJECT_SOURCE)):
        if entry and entry.get(key):
            return str(entry[key]), source

    return default, INSTANCE_SOURCE


def _flag(
    repository: dict[str, Any] | None,
    project: dict[str, Any] | None,
    default: bool,
) -> tuple[bool, str]:
    """The same, for the switch, where an explicit false is a decision."""
    for entry, source in ((repository, REPOSITORY_SOURCE), (project, PROJECT_SOURCE)):
        if entry and entry.get("enabled") is not None:
            return bool(entry["enabled"]), source

    return bool(default), INSTANCE_SOURCE


def resolve(
    config: dict[str, list[dict[str, Any]]], project_key: str, repository_slug: str
) -> Resolution:
    """The target one repository publishes to, field by field."""
    project = _project_entry(config, project_key)
    repository = _repository_entry(config, project_key, repository_slug)

    space_key, space_source = _field(
        repository, project, "space_key", settings.CONFLUENCE_SPACE_KEY or ""
    )
    parent_page_id, parent_source = _field(
        repository, project, "parent_page_id", settings.CONFLUENCE_PARENT_PAGE_ID or ""
    )
    enabled, enabled_source = _flag(repository, project, settings.CONFLUENCE_SYNC_ENABLED)

    return Resolution(
        space_key=space_key,
        parent_page_id=parent_page_id,
        enabled=enabled,
        space_source=space_source,
        parent_source=parent_source,
        enabled_source=enabled_source,
        project_target=project is not None,
        repository_target=repository is not None,
    )


def instance_defaults() -> dict[str, Any]:
    """The instance-wide target, which is what an unconfigured repository gets."""
    return {
        "space_key": settings.CONFLUENCE_SPACE_KEY or "",
        "parent_page_id": settings.CONFLUENCE_PARENT_PAGE_ID or "",
        "enabled": bool(settings.CONFLUENCE_SYNC_ENABLED),
    }


def describe(
    config: dict[str, list[dict[str, Any]]],
    identities: Iterable[tuple[str, str, str | None]],
) -> list[dict[str, Any]]:
    """Resolve every repository the settings page lists, for display.

    Each identity is the repository plus the application name it is registered
    under, and each row comes back with the values that would be used and the
    level each came from - so the page never has to work the fallback out for
    itself, and cannot disagree with what a sync would do.
    """
    rows: list[dict[str, Any]] = []
    for project_key, repository_slug, app_name in identities:
        rows.append(
            {
                "project_key": project_key,
                "repository_slug": repository_slug,
                "app_name": app_name,
                **resolve(config, project_key, repository_slug).as_dict(),
            }
        )

    return rows


async def load_targets(session: AsyncSession) -> dict[str, list[dict[str, Any]]]:
    """The stored configuration, or empty ones when it was never written."""
    result = await session.execute(
        select(SystemSetting).where(SystemSetting.setting_key == SETTING_KEY)
    )
    row = result.scalar_one_or_none()

    return parse_stored_targets(row.setting_value if row else "")
