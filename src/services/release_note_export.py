"""Release note export - one markdown document for one or more releases.

The document is assembled on the server so that the release notes page, an API
client and a CI job produce the same file. The notes are already stored markdown,
so what this module adds is packaging: the order, the metadata around each release,
the section separators and the filename.

Bodies are copied **verbatim**. The page linkifies JIRA keys and author mentions
when it renders; doing that here would make an export depend on the deployment's
JIRA settings and stop being diffable against what is stored.

The document holds no per-release metadata block on purpose: an exported change
log should read as notes rather than as a record of the database. The one thing
that stays is a marker in the section heading of a draft or a pre-release, because
notes that read as released while the release is not would be worse than a suffix.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.models.release_note import ReleaseNote, ReleaseNoteStatus


# A git tag may hold anything a ref allows; a filename may not.
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_REPEATED_DASHES = re.compile(r"-{2,}")

# Longest part of a filename taken from a project key, a slug or a tag.
MAX_FILENAME_PART = 80

EMPTY_BODY_PLACEHOLDER = "_No notes were written for this release._"
EMPTY_SELECTION_PLACEHOLDER = "_No releases were selected._"


@dataclass(frozen=True)
class ReleaseNoteExport:
    """A built export: the document plus what the caller should know about it."""

    filename: str
    content: str
    count: int
    skipped_ids: list[int] = field(default_factory=list)
    truncated: bool = False


def safe_filename_part(value: str | None) -> str:
    """Reduce a project key, repository slug or tag to filename-safe characters.

    A tag such as ``release/1.0.0`` or one holding spaces must not produce an
    invalid filename, and a value that carries nothing usable falls back to a
    neutral part instead of an empty one.
    """
    cleaned = _UNSAFE_FILENAME_CHARS.sub("-", (value or "").strip())
    cleaned = _REPEATED_DASHES.sub("-", cleaned).strip("-.")
    return cleaned[:MAX_FILENAME_PART] or "release"


def _resolve_exported_at(value: datetime | None) -> datetime:
    """The export instant, in UTC, defaulting to now."""
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def release_count_label(count: int) -> str:
    """``1 release`` / ``3 releases``."""
    return "1 release" if count == 1 else f"{count} releases"


def build_release_section(note: ReleaseNote) -> str:
    """Render one release as a document section.

    The heading carries the release name and its tag, unless the name is only a
    copy of the tag (the default when a release is drafted from a version), in
    which case repeating it would read as a mistake.

    A draft or a pre-release says so in that heading. The document deliberately
    holds no metadata block - an exported changelog should read as notes, not as a
    record - but notes that read as released while the release is not would be
    worse than a suffix.
    """
    tag = (note.tag_name or "").strip()
    name = (note.name or "").strip()
    heading = tag if not name or name == tag else f"{name} ({tag})"

    markers: list[str] = []
    if note.status != ReleaseNoteStatus.PUBLISHED:
        markers.append(str(note.status))
    if note.is_prerelease:
        markers.append("pre-release")
    if markers:
        heading = f"{heading} - {', '.join(markers)}"

    body = (note.body or "").strip()

    return f"## {heading}\n\n{body or EMPTY_BODY_PLACEHOLDER}"


def build_release_notes_document(
    releases: Sequence[ReleaseNote],
    *,
    project_key: str,
    repository_slug: str,
    exported_at: datetime | None = None,
) -> str:
    """Build the markdown document holding the given releases.

    The releases are expected in the order they should be read in (the service
    passes them newest first, like the release list). Sections are separated by a
    horizontal rule and the metadata is a bullet list rather than front matter: a
    stored body may itself contain ``---`` or ``##``, and the structure must not
    depend on markers the content can produce.
    """
    stamp = _resolve_exported_at(exported_at)
    coordinates = f"{project_key}/{repository_slug}"

    lines = [
        f"# Release notes - {coordinates}",
        "",
        (
            f"> {coordinates} - {release_count_label(len(releases))} - "
            f"exported from PyPRLedger on {stamp.strftime('%Y-%m-%d')}"
        ),
        "",
    ]

    if not releases:
        lines.append(EMPTY_SELECTION_PLACEHOLDER)
    else:
        sections = [build_release_section(note) for note in releases]
        lines.append("\n\n---\n\n".join(sections))

    return "\n".join(lines) + "\n"


def release_note_export_filename(
    releases: Sequence[ReleaseNote],
    *,
    project_key: str,
    repository_slug: str,
    exported_at: datetime | None = None,
) -> str:
    """Suggested filename: one release names itself, several are counted and dated."""
    project = safe_filename_part(project_key)
    repository = safe_filename_part(repository_slug)

    if len(releases) == 1:
        tag = safe_filename_part(releases[0].tag_name)
        return f"releasenotes-{project}-{repository}-{tag}.md"

    stamp = _resolve_exported_at(exported_at).strftime("%Y%m%d")
    return f"releasenotes-{project}-{repository}-{len(releases)}-releases-{stamp}.md"
