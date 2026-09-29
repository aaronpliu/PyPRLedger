"""Release note service - version releases and their generated notes.

The notes can be written by hand or drafted from the commits of the release
scope (everything between the previous version and the released version), which
reuses the release diff comparison against the git provider.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import NotFoundException
from src.models.auth_user import AuthUser
from src.models.release_note import ReleaseNote, ReleaseNoteStatus
from src.schemas.release_diff import ReleaseCompareRequest
from src.schemas.release_note import (
    REASON_PROVIDED,
    REASON_UNRESOLVED,
    SOURCE_EXPLICIT,
    SOURCE_NONE,
    SUMMARY_DETERMINISTIC,
    SUMMARY_LLM,
    SUMMARY_NOTICE_FAILED,
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
from src.services.release_note_scope_service import ReleaseNoteScopeService
from src.utils.timezone import get_current_time, utc_to_local


logger = logging.getLogger(__name__)


# Conventional commit type -> (section title, commit prefixes, section order).
#
# Sections follow Keep a Changelog (https://keepachangelog.com) so the generated
# notes use the same vocabulary as the project changelog:
#
#   Added       new features
#   Changed     changes to existing functionality
#   Deprecated  soon to be removed features
#   Removed     features removed in this version
#   Fixed       bug fixes
#   Security    security related fixes
#
# Documentation and Tests keep a section of their own, otherwise those commits
# would be buried in "Other Changes".
NOTE_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Added", ("feat", "feature", "add")),
    (
        "Changed",
        (
            "change",
            "improve",
            "impr",
            "refactor",
            "perf",
            "style",
            "build",
            "ci",
            "chore",
            "deps",
        ),
    ),
    ("Deprecated", ("deprecate", "deprecated")),
    ("Removed", ("remove", "removed", "revert")),
    ("Fixed", ("fix", "bugfix", "hotfix")),
    ("Security", ("security", "sec", "secure")),
    ("Documentation", ("docs", "doc")),
    ("Tests", ("test", "tests")),
)

OTHER_SECTION = "Other Changes"

# A commit message does not have to be a conventional commit to be placed. When
# the ``type:`` prefix is missing - or buried behind a ticket key - the wording of
# the subject decides, so a history that is not written in conventional commits is
# still grouped instead of landing in "Other Changes" as one flat list.
#
# Category-defining wording: when one of these appears the kind of change is
# decided, whatever verb leads the subject - "add tests" is a test, "fix a typo
# in the readme" is documentation. Latin and Chinese keywords sit in one table so
# a repository whose history is not in English is classified the same way.
STRONG_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Security", ("security", "vulnerability", "cve", "安全", "漏洞")),
    ("Deprecated", ("deprecate", "deprecated", "弃用", "废弃")),
    (
        "Removed",
        (
            "remove",
            "removed",
            "delete",
            "deleted",
            "drop",
            "dropped",
            "revert",
            "reverted",
            "删除",
            "移除",
            "回滚",
            "去掉",
        ),
    ),
    (
        "Tests",
        ("test", "tests", "testing", "coverage", "cover", "covered", "测试", "单测", "用例"),
    ),
    (
        "Documentation",
        (
            "doc",
            "docs",
            "document",
            "documented",
            "documentation",
            "readme",
            "changelog",
            "文档",
            "说明",
            "注释",
        ),
    ),
)

# Generic wording: none of the above, so the verb the author led with decides.
GENERIC_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Added",
        (
            "add",
            "added",
            "adds",
            "feat",
            "feature",
            "implement",
            "implemented",
            "introduce",
            "introduced",
            "support",
            "supported",
            "create",
            "created",
            "新增",
            "添加",
            "增加",
            "引入",
            "实现",
            "新建",
        ),
    ),
    (
        "Fixed",
        (
            "fix",
            "fixed",
            "fixes",
            "bugfix",
            "hotfix",
            "patch",
            "patched",
            "resolve",
            "resolved",
            "repair",
            "correct",
            "corrected",
            "修复",
            "修正",
            "解决",
            "修好",
        ),
    ),
    (
        "Changed",
        (
            "change",
            "changed",
            "update",
            "updated",
            "upgrade",
            "upgraded",
            "improve",
            "improved",
            "refactor",
            "refactored",
            "optimize",
            "optimise",
            "perf",
            "rename",
            "renamed",
            "migrate",
            "migrated",
            "bump",
            "bumped",
            "chore",
            "style",
            "build",
            "ci",
            "deps",
            "优化",
            "重构",
            "改进",
            "调整",
            "更新",
            "升级",
            "迁移",
            "重命名",
            "整理",
        ),
    ),
)

# Bookkeeping in front of the actual wording: a ticket key, a pull request number
# or a bracketed tag. Stripped before the subject is classified, and never removed
# from the rendered line - a ticket key there is what gets linked to JIRA.
NOISE_PREFIXES: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*[\[(]?[A-Z][A-Z0-9_]{1,9}-\d+[\])]?\s*[:：\-–]\s*"),
    re.compile(r"^\s*\(?#\d+\)?\s*[:：\-–]\s*"),
    re.compile(r"^\s*\[[^\[\]]{1,32}\]\s*"),
)
NOISE_PREFIX_PASSES = 3

# A merge commit is history bookkeeping: its subject describes the integration,
# while the commits it merged - which carry the change - are in the same scope.
# The patterns cover the messages git and the platforms write: "Merge branch 'x'",
# "Merge pull request #1 from ..." and "Merged in x (pull request #1)".
MERGE_SUBJECT_RE = re.compile(r"^merged?\b", re.IGNORECASE)

# Emoji each section is rendered with (one per Keep a Changelog category)
SECTION_EMOJI: dict[str, str] = {
    "Added": "✨",
    "Changed": "🔄",
    "Deprecated": "⚠️",
    "Removed": "🗑️",
    "Fixed": "🐛",
    "Security": "🔒",
    "Documentation": "📚",
    "Tests": "✅",
    OTHER_SECTION: "📝",
}

DEFAULT_LANGUAGE = "en"

# Section titles and the surrounding prose in the language of the caller. The
# section keys stay English: they are what the classifier and an LLM answer with.
SECTION_TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh-CN": {
        "Added": "新增",
        "Changed": "变更",
        "Deprecated": "弃用",
        "Removed": "移除",
        "Fixed": "修复",
        "Security": "安全",
        "Documentation": "文档",
        "Tests": "测试",
        OTHER_SECTION: "其他变更",
        "## What's Changed": "## 变更内容",
        "_No commits found in this release scope._": "_此发布范围没有提交。_",
    },
    "zh-TW": {
        "Added": "新增",
        "Changed": "變更",
        "Deprecated": "棄用",
        "Removed": "移除",
        "Fixed": "修復",
        "Security": "安全性",
        "Documentation": "文件",
        "Tests": "測試",
        OTHER_SECTION: "其他變更",
        "## What's Changed": "## 變更內容",
        "_No commits found in this release scope._": "_此發佈範圍沒有提交。_",
    },
}


def section_label(text: str, language: str | None) -> str:
    """Render one of the note's fixed strings in the caller's language."""
    translations = SECTION_TRANSLATIONS.get((language or DEFAULT_LANGUAGE).strip())
    return (translations or {}).get(text, text)


def strip_subject_noise(header: str) -> str:
    """Drop ticket keys / PR numbers in front of a commit subject."""
    stripped = header.strip()
    for _ in range(NOISE_PREFIX_PASSES):
        for pattern in NOISE_PREFIXES:
            candidate = pattern.sub("", stripped, count=1).strip()
            if candidate and candidate != stripped:
                stripped = candidate
                break
        else:
            break
    return stripped


def is_merge_commit(message: str | None) -> bool:
    """Whether a commit is a merge, which a release note never lists.

    The integration a merge performs is not a change of its own: what the release
    added is in the commits it merged, and those are in the same scope.
    """
    if not message:
        return False
    header = strip_subject_noise(message.split("\n", 1)[0].strip())
    return bool(MERGE_SUBJECT_RE.match(header))


def keyword_section(header: str) -> str | None:
    """Section implied by the wording of a subject.

    A category-defining word decides whatever verb leads the subject: "add tests"
    is a test, not a feature. Without one, the keyword the author led with wins -
    "update deps to fix a crash" is a change, "fix a crash while updating" is a
    fix.
    """
    lowered = header.lower()

    def earliest(table: tuple[tuple[str, tuple[str, ...]], ...]) -> tuple[int, str] | None:
        best: tuple[int, str] | None = None
        for section, keywords in table:
            for keyword in keywords:
                # a word boundary keeps "add" out of "address"; Chinese has none
                match = (
                    re.search(rf"\b{re.escape(keyword)}\b", lowered) if keyword.isascii() else None
                )
                index = match.start() if match else header.find(keyword)
                if index >= 0 and (best is None or index < best[0]):
                    best = (index, section)
        return best

    for table in (STRONG_KEYWORDS, GENERIC_KEYWORDS):
        found = earliest(table)
        if found is not None:
            return found[1]
    return None


def commit_section(message: str | None) -> str:
    """Map a commit message to its release note section.

    A conventional ``type:`` prefix decides when there is one; otherwise the
    wording of the subject does, so a history that is not written in conventional
    commits is still grouped into sections.
    """
    if not message:
        return OTHER_SECTION
    header = strip_subject_noise(message.split("\n", 1)[0].strip())
    if not header or is_merge_commit(header):
        return OTHER_SECTION

    # "feat(scope): add x" / "feat!: breaking change" -> "feat"
    prefix = header.split(":", 1)[0].strip().lower()
    prefix = prefix.split("(", 1)[0].rstrip("!")
    for title, prefixes in NOTE_SECTIONS:
        if prefix in prefixes:
            return title

    return keyword_section(header) or OTHER_SECTION


# JIRA ticket key: a project key (letter, then letters / digits / underscore) and a number
JIRA_TICKET_RE = re.compile(r"\b[A-Z][A-Z0-9_]{1,9}-\d+\b")


def jira_settings() -> tuple[str | None, set[str]]:
    """Configured JIRA base URL and the project keys allowed to be linked.

    Returns:
        ``(base_url, project_keys)``: the base URL without a trailing slash (``None``
        when JIRA is not configured) and the allowlist of project keys (empty when
        every ``PROJECT-123`` shaped key may be linked).
    """
    url = getattr(settings, "JIRA_BASE_URL", None)
    raw_keys = getattr(settings, "JIRA_PROJECT_KEYS", "") or ""
    return (
        url.rstrip("/") if url else None,
        {key.strip().upper() for key in raw_keys.split(",") if key.strip()},
    )


def linkify_jira_tickets(
    text: str | None,
    *,
    base_url: str | None = None,
    project_keys: Iterable[str] = (),
) -> str | None:
    """Link the JIRA ticket keys of a commit subject to ``{base_url}/browse/{KEY-123}``.

    Without a base URL the text is returned untouched. ``project_keys`` narrows the
    highlighting to the listed projects, which keeps look-alikes such as ``UTF-8``
    out of the notes.
    """
    if not text or not base_url:
        return text

    allowed = {key.upper() for key in project_keys}

    def replace(match: re.Match[str]) -> str:
        key = match.group(0)
        if allowed and key.rsplit("-", 1)[0].upper() not in allowed:
            return key
        return f"[{key}]({base_url}/browse/{key})"

    return JIRA_TICKET_RE.sub(replace, text)


def author_reference(commit: dict[str, Any]) -> str:
    """Author mention of a note line.

    A known provider account is shown as ``@login`` linked to its profile; commits
    without one (unmatched email, provider without profiles) keep the plain name.
    """
    username = commit.get("author_username")
    if username:
        handle = f"@{username}"
        url = commit.get("author_url")
        return f" by [{handle}]({url})" if url else f" by {handle}"

    name = commit.get("author_name")
    return f" by {name}" if name else ""


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
    compare_url: str | None = None,
    jira_base_url: str | None = None,
    jira_project_keys: Iterable[str] = (),
    language: str | None = None,
    summary: str | None = None,
) -> str:
    """Group commits into a changelog in the style of GitHub release notes.

    When ``compare_url`` is given the "Full Changelog" line links to the
    revision comparison on the git platform, otherwise the range stays plain text.
    Commit authors are mentioned as ``@login`` linked to their profile, and JIRA
    ticket keys are linked when ``jira_base_url`` is configured.

    ``summary`` is an optional paragraph - the one thing a reader wants before the
    list - rendered right under the heading. A commit may carry a ``section`` of
    its own, which is how a caller-supplied grouping (an LLM's, say) is honoured:
    the commit list itself stays the source of truth.

    Merge commits are left out: they are the integration of work that is listed
    through the commits they merged. A scope that holds nothing else renders as
    the empty scope it is.
    """
    grouped: dict[str, list[str]] = {}
    known_sections = {title for title, _ in NOTE_SECTIONS} | {OTHER_SECTION}

    for commit in commits:
        if is_merge_commit(commit.get("message")):
            continue
        section = commit.get("section")
        if section not in known_sections:
            section = commit_section(commit.get("message"))
        subject = commit_subject(commit.get("message")) or commit.get("id", "")[:7]
        subject = linkify_jira_tickets(
            subject, base_url=jira_base_url, project_keys=jira_project_keys
        )

        sha = commit.get("display_id") or str(commit.get("id", ""))[:7]
        url = commit.get("url")
        reference = f"[{sha}]({url})" if url else f"`{sha}`"

        author_part = author_reference(commit) if include_authors else ""

        grouped.setdefault(section, []).append(f"- {subject}{author_part} in {reference}")

    heading = section_label("## What's Changed", language)
    lines: list[str] = [heading, ""]

    if summary and summary.strip():
        lines.extend([summary.strip(), ""])

    if not grouped:
        lines.append(section_label("_No commits found in this release scope._", language))
        lines.append("")
    else:
        ordered_sections = [title for title, _ in NOTE_SECTIONS] + [OTHER_SECTION]
        for title in ordered_sections:
            entries = grouped.get(title)
            if not entries:
                continue
            label = section_label(title, language)
            lines.append(f"### {SECTION_EMOJI.get(title, '')} {label}".rstrip())
            lines.extend(entries)
            lines.append("")

    if previous_version:
        label = f"{previous_version}...{version}"
        if compare_url:
            lines.append(f"**Full Changelog**: [{label}]({compare_url})")
        else:
            lines.append(f"**Full Changelog**: `{label}`")

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
        scope_service: ReleaseNoteScopeService | None = None,
        provider_factory: Callable[[str], BaseGitProvider] = get_git_provider,
        llm_service: Any | None = None,
    ) -> None:
        self.db = db
        self._diff_service = diff_service or ReleaseDiffService()
        self._scope_service = scope_service or ReleaseNoteScopeService(
            provider_factory=provider_factory
        )
        self._provider_factory = provider_factory
        if llm_service is not None:
            self._llm_service = llm_service
        else:
            # Imported here: the summarizer classifies with the vocabulary above,
            # so importing it at module level would close a cycle.
            from src.services.release_note_llm_service import ReleaseNoteLlmService

            self._llm_service = ReleaseNoteLlmService(db=db)

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

    async def author_avatars(self, authors: Iterable[str | None]) -> dict[str, str]:
        """Map release authors to their profile picture URL.

        The author of a release is a username snapshot, so the picture is looked
        up on the local account. Authors without an account (releases imported
        from a git provider keep the provider login) or without an uploaded
        avatar are simply absent from the mapping.
        """
        usernames = {author for author in authors if author}
        if not usernames:
            return {}

        statement = select(AuthUser.username, AuthUser.avatar_url).where(
            AuthUser.username.in_(usernames),
            AuthUser.avatar_url.is_not(None),
        )
        rows = (await self.db.execute(statement)).all()
        return {username: avatar_url for username, avatar_url in rows if avatar_url}

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

    def compare_url(
        self,
        *,
        project_key: str,
        repository_slug: str,
        from_ref: str,
        to_ref: str,
        git_provider: str | None = None,
        workspace_slug: str | None = None,
    ) -> str | None:
        """Browsable comparison link for the release scope, when the platform has one.

        Building the URL is best effort: an unknown provider or a missing host must
        never fail the note generation, the range is then kept as plain text.
        """
        try:
            provider_name = resolve_provider_name(git_provider)
            provider = self._provider_factory(provider_name)
            remote_key = resolve_remote_project_key(project_key, provider_name, workspace_slug)
            return provider.web_compare_url(remote_key, repository_slug, from_ref, to_ref)
        except Exception as e:
            logger.warning(f"Could not build the release comparison link: {e}")
            return None

    def resolve_author_urls(
        self,
        commits: list[dict[str, Any]],
        *,
        git_provider: str | None = None,
    ) -> None:
        """Fill in the profile URL of the commit authors the provider knows.

        Best effort: a missing provider configuration must never fail the note
        generation, the author is then mentioned without a link.
        """
        pending = [
            commit
            for commit in commits
            if commit.get("author_username") and not commit.get("author_url")
        ]
        if not pending:
            return

        try:
            provider = self._provider_factory(resolve_provider_name(git_provider))
        except Exception as e:
            logger.warning(f"Could not resolve the commit author profiles: {e}")
            return

        for commit in pending:
            try:
                commit["author_url"] = provider.web_user_url(str(commit["author_username"]))
            except Exception as e:
                logger.warning(f"Could not build the author profile URL: {e}")

    async def generate_preview(
        self, request: ReleaseNotePreviewRequest
    ) -> ReleaseNotePreviewResponse:
        """Draft release notes from the commits of the release scope.

        The scope base is what the caller supplies, or - when none is supplied -
        the predecessor the server resolves from the repository's tags. Resolving it
        here is what keeps the notes of a tag in the middle of a long history from
        falling back to an enumeration of everything reachable from the tag.
        """
        previous_ref = (request.previous_version or "").strip() or None
        previous_sha: str | None = None
        version_sha: str | None = None
        previous_source = SOURCE_EXPLICIT if previous_ref else SOURCE_NONE
        previous_verified = bool(previous_ref)
        scope_reason = REASON_PROVIDED if previous_ref else REASON_UNRESOLVED

        if not previous_ref:
            scope = await self._scope_service.resolve(
                project_key=request.project_key,
                repository_slug=request.repository_slug,
                version=request.version,
                git_provider=request.git_provider,
                workspace_slug=request.workspace_slug,
                refresh=request.refresh,
            )
            previous_ref = scope.previous_ref
            previous_sha = scope.previous_sha
            version_sha = scope.version_sha
            previous_source = scope.source
            previous_verified = scope.verified
            scope_reason = scope.reason

        commits: list[dict[str, Any]] = []
        commit_count = 0
        truncated = False

        if previous_ref:
            # The release's own commits are exactly the ones the new version adds on
            # top of its predecessor, asked as one provider difference. The repository
            # baseline is deliberately ignored: notes are scoped by the predecessor.
            # The revisions are used when known so a tag moved between resolving the
            # scope and comparing cannot change what the notes are built from.
            comparison = await self._diff_service.compare_releases(
                ReleaseCompareRequest(
                    project_key=request.project_key,
                    repository_slug=request.repository_slug,
                    workspace_slug=request.workspace_slug,
                    git_provider=request.git_provider,
                    source_ref=previous_sha or previous_ref,
                    target_ref=version_sha or request.version,
                    include_commits=True,
                    use_stored_baseline=False,
                    scan_limit=min(max(request.max_commits, 1), 10000),
                    render_limit=min(max(request.max_commits, 1), 2000),
                )
            )
            commits = [commit.model_dump() for commit in comparison.added_commits]
            # the scope size is exact when the difference was scanned completely;
            # the returned list may still be trimmed for display
            commit_count = max(comparison.added_count, len(commits))
            truncated = len(commits) < commit_count or not comparison.added_complete
        else:
            # No predecessor to difference against: either the tag is the first
            # release of its line, or the scope could not be resolved. The history
            # is listed as the fallback, and the response says which of the two it is
            # so a capped listing is not read as a repository problem.
            version_commits, capped = await self._diff_service.list_release_commits(
                project_key=request.project_key,
                repository_slug=request.repository_slug,
                git_provider=request.git_provider,
                workspace_slug=request.workspace_slug,
                ref=request.version,
                limit=request.max_commits,
            )
            commits = [commit.model_dump() for commit in version_commits]
            commit_count = len(commits)
            truncated = capped

        compare_url = (
            self.compare_url(
                project_key=request.project_key,
                repository_slug=request.repository_slug,
                from_ref=previous_ref,
                to_ref=request.version,
                git_provider=request.git_provider,
                workspace_slug=request.workspace_slug,
            )
            if previous_ref
            else None
        )

        self.resolve_author_urls(commits, git_provider=request.git_provider)

        summary, summary_source, summary_notice, summary_error = await self._summarize(
            request, commits, previous_ref
        )

        jira_base_url, jira_project_keys = jira_settings()

        body = build_release_notes_markdown(
            commits,
            version=request.version,
            previous_version=previous_ref,
            include_authors=request.include_authors,
            compare_url=compare_url,
            jira_base_url=jira_base_url,
            jira_project_keys=jira_project_keys,
            language=request.language,
            summary=summary,
        )

        return ReleaseNotePreviewResponse(
            version=request.version,
            previous_version=previous_ref,
            previous_sha=previous_sha,
            version_sha=version_sha,
            previous_source=previous_source,
            previous_verified=previous_verified,
            scope_reason=scope_reason,
            suggested_name=request.version,
            body=body,
            commit_count=commit_count,
            commits=commits,
            truncated=truncated,
            summary=summary,
            summary_source=summary_source,
            summary_notice=summary_notice,
            summary_error=summary_error,
        )

    async def _summarize(
        self,
        request: ReleaseNotePreviewRequest,
        commits: list[dict[str, Any]],
        previous_ref: str | None,
    ) -> tuple[str | None, str, str | None]:
        """Optional LLM pass: a summary paragraph and a section per commit.

        Answers ``(summary, source, notice, detail)``. The commit list stays the
        source of truth - the model only answers about the ids it was given - and
        anything that goes wrong is answered with the deterministic notes rather
        than with an error. ``notice`` says why there is no summary, so that a
        pass that was asked for and failed is not mistaken for one that was never
        asked for, and ``detail`` is what the provider said when it refused.
        """
        if not request.summarize:
            return None, SUMMARY_DETERMINISTIC, None, None

        try:
            outcome = await self._llm_service.summarize(
                project_key=request.project_key,
                repository_slug=request.repository_slug,
                version=request.version,
                previous_version=previous_ref,
                commits=commits,
                language=request.language,
            )
        except Exception as e:  # noqa: BLE001 - an optional pass must never fail the notes
            logger.warning(f"Release note summarization failed: {e}")
            return None, SUMMARY_DETERMINISTIC, SUMMARY_NOTICE_FAILED, None

        summary = outcome.summary
        if summary is None:
            return None, SUMMARY_DETERMINISTIC, outcome.notice, outcome.detail

        for commit in commits:
            section = summary.sections.get(str(commit.get("id")))
            if section:
                commit["section"] = section
        return summary.summary or None, SUMMARY_LLM, None, None
