"""Release note service - version releases and their generated notes.

The notes can be written by hand or drafted from the commits of the release
scope (everything between the previous version and the released version), which
reuses the release diff comparison against the git provider.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundException
from src.models.release_note import ReleaseNote, ReleaseNoteStatus
from src.schemas.release_diff import ReleaseCompareRequest
from src.schemas.release_note import (
    ReleaseNoteCreateRequest,
    ReleaseNoteImportRequest,
    ReleaseNotePreviewRequest,
    ReleaseNotePreviewResponse,
    ReleaseNotePushRequest,
    ReleaseNoteUpdateRequest,
)
from src.services.git_providers import BaseGitProvider, get_git_provider
from src.services.release_diff_service import (
    ReleaseDiffService,
    resolve_provider_name,
    resolve_remote_project_key,
)
from src.utils.timezone import get_current_time, utc_to_local


logger = logging.getLogger(__name__)


# Conventional commit type -> (section title, section order)
NOTE_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Features", ("feat", "feature")),
    ("Bug Fixes", ("fix", "bugfix")),
    ("Performance", ("perf",)),
    ("Refactoring", ("refactor",)),
    ("Documentation", ("docs", "doc")),
    ("Tests", ("test", "tests")),
    ("Maintenance", ("build", "ci", "chore", "style", "deps")),
    ("Reverts", ("revert",)),
)

OTHER_SECTION = "Other Changes"
SECTION_EMOJI: dict[str, str] = {
    "Features": "🚀",
    "Bug Fixes": "🐛",
    "Performance": "⚡",
    "Refactoring": "♻️",
    "Documentation": "📚",
    "Tests": "✅",
    "Maintenance": "🔧",
    "Reverts": "⏪",
    OTHER_SECTION: "📝",
}


def commit_section(message: str | None) -> str:
    """Map a commit message to its release note section (conventional commits)."""
    if not message:
        return OTHER_SECTION
    header = message.split("\n", 1)[0].strip()
    # "feat(scope): add x" / "feat!: breaking change" -> "feat"
    prefix = header.split(":", 1)[0].strip().lower()
    prefix = prefix.split("(", 1)[0].rstrip("!")
    for title, prefixes in NOTE_SECTIONS:
        if prefix in prefixes:
            return title
    return OTHER_SECTION


def commit_subject(message: str | None) -> str:
    """First line of the commit, with the conventional prefix stripped."""
    if not message:
        return ""
    header = message.split("\n", 1)[0].strip()
    if ":" in header:
        prefix, rest = header.split(":", 1)
        if prefix.strip().lower().split("(", 1)[0].rstrip("!") in {
            p for _, prefixes in NOTE_SECTIONS for p in prefixes
        }:
            return rest.strip()
    return header


def build_release_notes_markdown(
    commits: list[dict[str, Any]],
    *,
    version: str,
    previous_version: str | None = None,
    include_authors: bool = True,
) -> str:
    """Group commits into a changelog in the style of GitHub release notes."""
    grouped: dict[str, list[str]] = {}

    for commit in commits:
        section = commit_section(commit.get("message"))
        subject = commit_subject(commit.get("message")) or commit.get("id", "")[:7]

        sha = commit.get("display_id") or str(commit.get("id", ""))[:7]
        url = commit.get("url")
        reference = f"[{sha}]({url})" if url else f"`{sha}`"

        author = commit.get("author_name")
        author_part = f" by {author}" if include_authors and author else ""

        grouped.setdefault(section, []).append(f"- {subject}{author_part} in {reference}")

    lines: list[str] = ["## What's Changed", ""]

    if not commits:
        lines.append("_No commits found in this release scope._")
        lines.append("")
    else:
        ordered_sections = [title for title, _ in NOTE_SECTIONS] + [OTHER_SECTION]
        for title in ordered_sections:
            entries = grouped.get(title)
            if not entries:
                continue
            lines.append(f"### {SECTION_EMOJI.get(title, '')} {title}".rstrip())
            lines.extend(entries)
            lines.append("")

    if previous_version:
        lines.append(f"**Full Changelog**: `{previous_version}...{version}`")

    return "\n".join(lines).strip() + "\n"


def parse_provider_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp coming from a git provider (localized)."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning(f"Unparsable provider timestamp: {value}")
        return None
    if parsed.tzinfo is None:
        return parsed
    return utc_to_local(parsed)


class ReleaseNoteService:
    """Business logic for version releases."""

    def __init__(
        self,
        db: AsyncSession,
        diff_service: ReleaseDiffService | None = None,
        provider_factory: Callable[[str], BaseGitProvider] = get_git_provider,
    ) -> None:
        self.db = db
        self._diff_service = diff_service or ReleaseDiffService()
        self._provider_factory = provider_factory

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    async def list_notes(
        self,
        *,
        project_key: str,
        repository_slug: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ReleaseNote], int]:
        """List releases of a repository, newest release first."""
        filters = [
            ReleaseNote.project_key == project_key,
            ReleaseNote.repository_slug == repository_slug,
        ]
        if status:
            filters.append(ReleaseNote.status == status)

        total = (
            await self.db.execute(select(func.count(ReleaseNote.id)).where(*filters))
        ).scalar_one()

        statement = (
            select(ReleaseNote)
            .where(*filters)
            .order_by(func.coalesce(ReleaseNote.published_date, ReleaseNote.updated_date).desc())
            .limit(limit)
            .offset(offset)
        )
        notes = list((await self.db.execute(statement)).scalars().all())
        return notes, int(total or 0)

    async def latest_published_id(self, *, project_key: str, repository_slug: str) -> int | None:
        """Id of the latest published, non pre-release version (GitHub 'Latest')."""
        statement = (
            select(ReleaseNote.id)
            .where(
                ReleaseNote.project_key == project_key,
                ReleaseNote.repository_slug == repository_slug,
                ReleaseNote.status == ReleaseNoteStatus.PUBLISHED,
                ReleaseNote.is_prerelease.is_(False),
            )
            .order_by(ReleaseNote.published_date.desc(), ReleaseNote.id.desc())
            .limit(1)
        )
        return (await self.db.execute(statement)).scalar_one_or_none()

    async def get_note(self, note_id: int) -> ReleaseNote | None:
        """Fetch one release by id."""
        return (
            await self.db.execute(select(ReleaseNote).where(ReleaseNote.id == note_id))
        ).scalar_one_or_none()

    async def get_note_by_tag(
        self, *, project_key: str, repository_slug: str, tag_name: str
    ) -> ReleaseNote | None:
        """Fetch one release by its tag name."""
        statement = select(ReleaseNote).where(
            ReleaseNote.project_key == project_key,
            ReleaseNote.repository_slug == repository_slug,
            ReleaseNote.tag_name == tag_name,
        )
        return (await self.db.execute(statement)).scalar_one_or_none()

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #

    async def create_note(
        self,
        request: ReleaseNoteCreateRequest,
        *,
        author: str | None = None,
    ) -> ReleaseNote:
        """Create a draft or publish a version release."""
        tag_name = request.tag_name.strip()
        existing = await self.get_note_by_tag(
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            tag_name=tag_name,
        )
        if existing:
            raise ValueError(
                f"Release '{tag_name}' already exists for "
                f"{request.project_key}/{request.repository_slug}"
            )

        note = ReleaseNote(
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            tag_name=tag_name,
            name=(request.name or tag_name).strip(),
            body=request.body or "",
            previous_tag=request.previous_tag,
            status=request.status,
            is_prerelease=request.is_prerelease,
            author=author,
        )
        if request.status == ReleaseNoteStatus.PUBLISHED:
            note.published_date = get_current_time()

        self.db.add(note)
        await self.db.flush()
        logger.info(
            f"Release note created: {tag_name} "
            f"({request.project_key}/{request.repository_slug}, status={request.status})"
        )
        return note

    async def update_note(
        self,
        note_id: int,
        request: ReleaseNoteUpdateRequest,
        *,
        author: str | None = None,
    ) -> ReleaseNote | None:
        """Update a release; publishing stamps the publish date once."""
        note = await self.get_note(note_id)
        if not note:
            return None

        if request.name is not None:
            note.name = request.name.strip() or note.tag_name
        if request.body is not None:
            note.body = request.body
        if request.previous_tag is not None:
            note.previous_tag = request.previous_tag or None
        if request.is_prerelease is not None:
            note.is_prerelease = request.is_prerelease
        if request.status is not None:
            if request.status == ReleaseNoteStatus.PUBLISHED and not note.published_date:
                note.published_date = get_current_time()
            if request.status == ReleaseNoteStatus.PUBLISHED and author:
                note.author = author
            note.status = request.status

        await self.db.flush()
        return note

    async def delete_note(self, note_id: int) -> bool:
        """Delete a release."""
        note = await self.get_note(note_id)
        if not note:
            return False
        await self.db.delete(note)
        await self.db.flush()
        return True

    # ------------------------------------------------------------------ #
    # Provider integration (GitHub Enterprise Releases)
    # ------------------------------------------------------------------ #

    def _release_provider(self, git_provider: str | None) -> tuple[str, BaseGitProvider]:
        """Resolve the provider and make sure it exposes a release API."""
        provider_name = resolve_provider_name(git_provider)
        provider = self._provider_factory(provider_name)
        if not provider.supports_releases:
            raise ValueError(
                f"Git provider '{provider_name}' does not support releases - "
                "the version release stays in PyPRLedger"
            )
        return provider_name, provider

    async def push_to_provider(
        self, note_id: int, request: ReleaseNotePushRequest
    ) -> ReleaseNote | None:
        """Publish a stored release on the git provider and remember where.

        Existing provider releases are updated when ``update_existing`` is set
        (falling back to a create when the provider release disappeared).
        """
        note = await self.get_note(note_id)
        if not note:
            return None

        provider_name, provider = self._release_provider(request.git_provider)
        remote_key = resolve_remote_project_key(
            request.project_key, provider_name, request.workspace_slug
        )

        release: dict[str, Any] | None = None
        if note.external_id and request.update_existing:
            try:
                release = await provider.update_release(
                    remote_key,
                    request.repository_slug,
                    note.external_id,
                    name=note.name,
                    body=note.body,
                    prerelease=note.is_prerelease,
                )
            except NotFoundException:
                logger.warning(
                    f"Provider release {note.external_id} for {note.tag_name} is gone, recreating"
                )

        if release is None:
            release = await provider.create_release(
                remote_key,
                request.repository_slug,
                tag_name=note.tag_name,
                name=note.name,
                body=note.body,
                target_commitish=request.target_commitish,
                prerelease=note.is_prerelease,
            )

        note.external_provider = provider_name
        note.external_id = str(release.get("id") or "") or None
        note.external_url = release.get("html_url") or None
        await self.db.flush()
        logger.info(
            f"Release {note.tag_name} pushed to {provider_name}: {note.external_url or '-'}"
        )
        return note

    async def import_from_provider(
        self, request: ReleaseNoteImportRequest
    ) -> tuple[int, int, int, list[ReleaseNote]]:
        """Import the releases of a repository from the git provider.

        Returns:
            Tuple of (imported, updated, skipped, notes).
        """
        provider_name, provider = self._release_provider(request.git_provider)
        remote_key = resolve_remote_project_key(
            request.project_key, provider_name, request.workspace_slug
        )

        releases = await provider.list_releases(
            remote_key, request.repository_slug, limit=request.limit
        )

        imported = updated = skipped = 0
        items: list[ReleaseNote] = []

        for release in releases:
            tag_name = str(release.get("tag_name") or "").strip()
            if not tag_name:
                skipped += 1
                continue

            existing = await self.get_note_by_tag(
                project_key=request.project_key,
                repository_slug=request.repository_slug,
                tag_name=tag_name,
            )
            if existing and not request.overwrite:
                skipped += 1
                continue

            is_draft = bool(release.get("draft"))
            fields: dict[str, Any] = {
                "name": release.get("name") or tag_name,
                "body": release.get("body") or "",
                "is_prerelease": bool(release.get("prerelease")),
                "status": ReleaseNoteStatus.DRAFT if is_draft else ReleaseNoteStatus.PUBLISHED,
                "published_date": parse_provider_datetime(release.get("published_at")),
                "author": release.get("author"),
                "external_provider": provider_name,
                "external_id": str(release.get("id") or "") or None,
                "external_url": release.get("html_url") or None,
            }

            if existing:
                for field, value in fields.items():
                    setattr(existing, field, value)
                if not is_draft and not existing.published_date:
                    existing.published_date = get_current_time()
                await self.db.flush()
                note = existing
                updated += 1
            else:
                note = ReleaseNote(
                    project_key=request.project_key,
                    repository_slug=request.repository_slug,
                    tag_name=tag_name,
                    **fields,
                )
                if not is_draft and not note.published_date:
                    note.published_date = get_current_time()
                self.db.add(note)
                await self.db.flush()
                imported += 1

            items.append(note)

        logger.info(
            f"Imported releases from {provider_name} for "
            f"{request.project_key}/{request.repository_slug}: "
            f"{imported} new, {updated} updated, {skipped} skipped"
        )
        return imported, updated, skipped, items

    # ------------------------------------------------------------------ #
    # Note generation
    # ------------------------------------------------------------------ #

    async def generate_preview(
        self, request: ReleaseNotePreviewRequest
    ) -> ReleaseNotePreviewResponse:
        """Draft release notes from the commits of the release scope."""
        commits: list[dict[str, Any]] = []
        truncated = False

        if request.previous_version:
            comparison = await self._diff_service.compare_releases(
                ReleaseCompareRequest(
                    project_key=request.project_key,
                    repository_slug=request.repository_slug,
                    workspace_slug=request.workspace_slug,
                    git_provider=request.git_provider,
                    old_release_ref=request.previous_version,
                    new_release_ref=request.version,
                    include_commits=True,
                    max_commits=request.max_commits,
                )
            )
            commits = [commit.model_dump() for commit in comparison.added_commits]
            truncated = comparison.truncated
        else:
            version_commits, truncated = await self._diff_service.list_release_commits(
                project_key=request.project_key,
                repository_slug=request.repository_slug,
                git_provider=request.git_provider,
                workspace_slug=request.workspace_slug,
                ref=request.version,
                limit=request.max_commits,
            )
            commits = [commit.model_dump() for commit in version_commits]

        body = build_release_notes_markdown(
            commits,
            version=request.version,
            previous_version=request.previous_version,
            include_authors=request.include_authors,
        )

        return ReleaseNotePreviewResponse(
            version=request.version,
            previous_version=request.previous_version,
            suggested_name=request.version,
            body=body,
            commit_count=len(commits),
            commits=commits,
            truncated=truncated,
        )
