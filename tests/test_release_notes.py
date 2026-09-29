"""Tests for release notes (version releases).

The git provider is never contacted: the note generator is wired to a stub diff
service and the CRUD tests use the in-memory SQLite fixture.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.endpoints.release_notes import get_rbac_service, get_release_note_service
from src.core.config import settings
from src.core.database import get_db_session
from src.core.exceptions import NotFoundException
from src.core.git_provider import GitProvider
from src.core.permissions import get_current_user_with_token
from src.main import app
from src.models.auth_user import AuthUser
from src.schemas.release_diff import CommitInfo
from src.schemas.release_note import (
    REASON_FIRST_RELEASE,
    REASON_PROVIDED,
    REASON_RESOLVED,
    REASON_UNRESOLVED,
    SOURCE_ANCESTOR,
    SOURCE_EXPLICIT,
    SOURCE_NAME_ORDER,
    SOURCE_NONE,
    ReleaseNoteCreateRequest,
    ReleaseNoteImportRequest,
    ReleaseNotePreviewRequest,
    ReleaseNotePushRequest,
    ReleaseNoteUpdateRequest,
)
from src.services.git_providers.base import BaseGitProvider
from src.services.release_note_scope_service import ReleaseScope
from src.services.release_note_service import (
    NOTE_SECTIONS,
    OTHER_SECTION,
    SECTION_EMOJI,
    ReleaseNoteService,
    author_reference,
    build_release_notes_markdown,
    commit_section,
    commit_subject,
    is_merge_commit,
    jira_settings,
    linkify_jira_tickets,
    parse_provider_datetime,
)


C1 = "1111111111111111111111111111111111111111"
C2 = "2222222222222222222222222222222222222222"
C3 = "3333333333333333333333333333333333333333"
C4 = "4444444444444444444444444444444444444444"
C5 = "5555555555555555555555555555555555555555"
C6 = "6666666666666666666666666666666666666666"


def commit(
    sha: str, message: str, author: str | None = "Jane Doe", url: str | None = None
) -> CommitInfo:
    return CommitInfo(
        id=sha,
        display_id=sha[:7],
        author_name=author,
        message=message,
        url=url or f"https://git.local/commits/{sha[:7]}",
    )


class StubDiffService:
    """Stands in for ReleaseDiffService (no provider traffic)."""

    def __init__(
        self,
        added: list[CommitInfo] | None = None,
        truncated: bool = False,
        added_count: int | None = None,
    ) -> None:
        self._added = added or []
        self._truncated = truncated
        # the size of the scope, which can exceed the returned (trimmed) list
        self._added_count = len(self._added) if added_count is None else added_count
        self.compare_calls: list[Any] = []
        self.list_calls: list[dict[str, Any]] = []

    async def compare_releases(self, request: Any) -> Any:
        self.compare_calls.append(request)
        return type(
            "Comparison",
            (),
            {
                "added_commits": self._added,
                "added_count": self._added_count,
                "added_complete": not self._truncated,
            },
        )()

    async def list_release_commits(self, **kwargs: Any) -> tuple[list[CommitInfo], bool]:
        self.list_calls.append(kwargs)
        return self._added, self._truncated


class StubProvider(BaseGitProvider):
    """Git provider stub exposing the release API (GitHub Enterprise shape)."""

    def __init__(self, supports_releases: bool = True) -> None:
        self._supports_releases = supports_releases
        self.created: list[dict[str, Any]] = []
        self.updated: list[dict[str, Any]] = []
        self.releases: list[dict[str, Any]] = []
        self.fail_update_with_not_found = False

    @property
    def name(self) -> str:
        return GitProvider.GITHUB_ENTERPRISE.value

    @property
    def supports_releases(self) -> bool:
        return self._supports_releases

    async def get_project_info(self, project_key: str) -> dict[str, Any] | None:
        return None

    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict[str, Any] | None:
        return None

    async def get_user_info(self, username: str) -> dict[str, Any] | None:
        return None

    async def list_releases(
        self, project_key: str, repository_slug: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        return self.releases[:limit]

    async def create_release(
        self,
        project_key: str,
        repository_slug: str,
        *,
        tag_name: str,
        name: str,
        body: str = "",
        target_commitish: str | None = None,
        draft: bool = False,
        prerelease: bool = False,
    ) -> dict[str, Any]:
        self.created.append(
            {
                "project_key": project_key,
                "repository_slug": repository_slug,
                "tag_name": tag_name,
                "name": name,
                "body": body,
                "target_commitish": target_commitish,
                "draft": draft,
                "prerelease": prerelease,
            }
        )
        return {
            "id": "1001",
            "tag_name": tag_name,
            "name": name,
            "body": body,
            "prerelease": prerelease,
            "html_url": f"https://github.local/{project_key}/{repository_slug}/releases/tag/{tag_name}",
        }

    async def update_release(
        self,
        project_key: str,
        repository_slug: str,
        release_id: str,
        *,
        name: str | None = None,
        body: str | None = None,
        prerelease: bool | None = None,
    ) -> dict[str, Any]:
        if self.fail_update_with_not_found:
            raise NotFoundException(f"GitHub resource not found: release {release_id}")
        self.updated.append(
            {"release_id": release_id, "name": name, "body": body, "prerelease": prerelease}
        )
        return {
            "id": release_id,
            "tag_name": "v1.1.0",
            "name": name,
            "body": body,
            "prerelease": prerelease,
            "html_url": f"https://github.local/{project_key}/{repository_slug}/releases/{release_id}",
        }


class ComparingProvider(StubProvider):
    """Stub provider that can address a revision comparison remotely."""

    def __init__(
        self,
        url: str | None = "https://github.local/PROJ/my-repo/compare/v1.0.0...v1.1.0",
    ) -> None:
        super().__init__()
        self._compare_url = url
        self.compare_url_calls: list[tuple[str, str, str, str]] = []

    def web_compare_url(
        self, project_key: str, repository_slug: str, from_ref: str, to_ref: str
    ) -> str | None:
        self.compare_url_calls.append((project_key, repository_slug, from_ref, to_ref))
        return self._compare_url

    def web_user_url(self, username: str) -> str | None:
        return f"https://github.local/{username}"


class StubRBAC:
    """RBAC stub returning a fixed permission decision."""

    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.checks: list[dict[str, Any]] = []

    async def check_permission(self, **kwargs: Any) -> bool:
        self.checks.append(kwargs)
        return self.allowed


def build_service(
    db: AsyncSession,
    diff: StubDiffService | None = None,
    provider: StubProvider | None = None,
    scope: Any | None = None,
) -> ReleaseNoteService:
    stub = provider or StubProvider()
    return ReleaseNoteService(
        db,
        diff_service=diff or StubDiffService(),  # type: ignore[arg-type]
        scope_service=scope,
        provider_factory=lambda _name: stub,
    )


class StubScopeService:
    """Stands in for ReleaseNoteScopeService (fixed answer, no provider traffic)."""

    def __init__(self, scope: ReleaseScope) -> None:
        self.scope = scope
        self.calls: list[dict[str, Any]] = []

    async def resolve(self, **kwargs: Any) -> ReleaseScope:
        self.calls.append(kwargs)
        return self.scope


class TagListingProvider(ComparingProvider):
    """Stub provider that can list tags with their revisions and verify ancestry."""

    def __init__(
        self,
        tags: list[dict[str, Any]] | None = None,
        ancestors: tuple[str, ...] = (),
    ) -> None:
        super().__init__()
        self.tags = tags or []
        self.ancestors = set(ancestors)
        self.tag_calls = 0
        self.probes: list[tuple[str, str]] = []

    async def list_tags_with_commits(
        self, project_key: str, repository_slug: str, limit: int = 1000
    ) -> list[dict[str, Any]]:
        self.tag_calls += 1
        return self.tags[:limit]

    async def contains_commit(
        self, project_key: str, repository_slug: str, ref: str, commit: str
    ) -> bool:
        self.probes.append((ref, commit))
        return commit in self.ancestors


def create_payload(**overrides: Any) -> ReleaseNoteCreateRequest:
    payload: dict[str, Any] = {
        "project_key": "PROJ",
        "repository_slug": "my-repo",
        "tag_name": "v1.0.0",
        "name": "First release",
        "body": "## What's Changed\n\n- initial",
        "status": "draft",
    }
    payload.update(overrides)
    return ReleaseNoteCreateRequest(**payload)


# --------------------------------------------------------------------------- #
# Markdown generation
# --------------------------------------------------------------------------- #


def test_commit_section_maps_conventional_types_to_changelog_categories() -> None:
    # Keep a Changelog vocabulary
    assert commit_section("feat(api): add endpoint") == "Added"
    assert commit_section("fix: crash") == "Fixed"
    assert commit_section("security: rotate tokens") == "Security"
    assert commit_section("deprecate: legacy export") == "Deprecated"
    assert commit_section("revert: drop widget") == "Removed"
    assert commit_section("remove: drop widget") == "Removed"

    # every non functional change (breaking or not) lands in Changed
    assert commit_section("improve: faster list") == "Changed"
    assert commit_section("perf!: faster") == "Changed"
    assert commit_section("refactor: split module") == "Changed"
    assert commit_section("chore: bump deps") == "Changed"

    # documentation and tests keep a section of their own
    assert commit_section("docs: update readme") == "Documentation"
    assert commit_section("test: cover the upsert") == "Tests"

    # a subject that says nothing about the kind of change stays ungrouped
    assert commit_section("release 2.2601.5") == "Other Changes"
    assert commit_section(None) == "Other Changes"


def test_commit_section_groups_subjects_without_a_conventional_prefix() -> None:
    """A history that is not written in conventional commits is still grouped."""
    # the wording decides when there is no "type:" prefix
    assert commit_section("fix crash on logout") == "Fixed"
    assert commit_section("Add support for SSO") == "Added"
    assert commit_section("update the deploy script") == "Changed"
    assert commit_section("delete the legacy importer") == "Removed"
    assert commit_section("document the webhook payload") == "Documentation"
    assert commit_section("cover the upsert path") == "Tests"

    # the keyword the author led with wins
    assert commit_section("update deps to fix the crash") == "Changed"
    assert commit_section("fix the crash while updating") == "Fixed"


def test_commit_section_looks_behind_ticket_and_pr_prefixes() -> None:
    """A ticket key or a PR number in front of the wording does not hide it."""
    assert commit_section("PRL-123: fix crash on logout") == "Fixed"
    assert commit_section("[PRL-123] fix crash on logout") == "Fixed"
    assert commit_section("PRL-123 - fix crash on logout") == "Fixed"
    assert commit_section("#42: add the dashboard") == "Added"
    assert commit_section("[hotfix] 修复登录崩溃") == "Fixed"

    # and it is not removed from the rendered line - that is what gets linked
    assert commit_subject("PRL-123: fix crash on logout") == "PRL-123: fix crash on logout"


def test_commit_section_understands_chinese_subjects() -> None:
    assert commit_section("修复登录崩溃") == "Fixed"
    assert commit_section("新增导出功能") == "Added"
    assert commit_section("重构导出模块") == "Changed"
    assert commit_section("补充接口文档") == "Documentation"


def test_commit_section_keeps_merge_commits_ungrouped() -> None:
    """A merge subject describes the integration, not the change it carries."""
    assert commit_section("Merge pull request #42 from acme/feature/sso") == "Other Changes"
    assert commit_section("Merge branch 'release/1.0' into main") == "Other Changes"


def test_is_merge_commit_reads_the_messages_git_and_the_platforms_write() -> None:
    """Every wording a merge commit is given describes an integration."""
    assert is_merge_commit("Merge branch 'release/1.0' into main")
    assert is_merge_commit("Merge remote-tracking branch 'origin/main'")
    assert is_merge_commit("Merge pull request #42 from acme/feature/sso")
    # Bitbucket Server writes the merge the other way around
    assert is_merge_commit("Merged in feature/sso (pull request #42)")
    # a ticket key in front of it does not hide it
    assert is_merge_commit("PRL-123: Merge branch 'main'")
    assert is_merge_commit("[PRL-123] Merge branch 'main'")
    assert is_merge_commit("Merge branch 'main' into feature/sso\n\nSome body")

    assert not is_merge_commit("feat: merge the two report makers")
    assert not is_merge_commit("Merger of the export pipelines")
    assert not is_merge_commit("")
    assert not is_merge_commit(None)


def test_section_emoji_covers_every_produced_section() -> None:
    # one emoji per Keep a Changelog category
    for category in ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"):
        assert category in SECTION_EMOJI
        assert SECTION_EMOJI[category]

    produced = {title for title, _ in NOTE_SECTIONS} | {OTHER_SECTION}
    assert produced <= set(SECTION_EMOJI)


def test_commit_subject_strips_the_conventional_prefix() -> None:
    assert commit_subject("feat(api): add endpoint") == "add endpoint"
    assert commit_subject("fix: crash on logout") == "crash on logout"
    assert commit_subject("plain message") == "plain message"
    assert commit_subject(None) == ""


def test_build_markdown_groups_commits_and_appends_the_changelog_link() -> None:
    commits = [
        commit(C1, "feat: add login page").model_dump(),
        commit(C2, "fix: crash on logout", author="John Roe").model_dump(),
        commit(C3, "docs: update readme", author=None).model_dump(),
    ]

    body = build_release_notes_markdown(commits, version="v1.1.0", previous_version="v1.0.0")

    assert body.startswith("## What's Changed")
    assert "### ✨ Added" in body
    assert "### 🐛 Fixed" in body
    assert "### 📚 Documentation" in body
    assert "- add login page by Jane Doe in [1111111](https://git.local/commits/1111111)" in body
    assert "- crash on logout by John Roe in [2222222](https://git.local/commits/2222222)" in body
    # section order: added before fixed
    assert body.index("Added") < body.index("Fixed")
    assert "**Full Changelog**: `v1.0.0...v1.1.0`" in body


def test_build_markdown_renders_the_changelog_categories_in_order() -> None:
    commits = [
        commit(C1, "revert: drop old widget").model_dump(),
        commit(C2, "security: rotate tokens").model_dump(),
        commit(C3, "fix: crash on logout").model_dump(),
        commit(C4, "deprecate: legacy export").model_dump(),
        commit(C5, "perf: cache tags").model_dump(),
        commit(C6, "feat: add login page").model_dump(),
    ]

    body = build_release_notes_markdown(commits, version="v1.2.0")

    # Keep a Changelog order, whatever the commit order is
    headings = [
        "### ✨ Added",
        "### 🔄 Changed",
        "### ⚠️ Deprecated",
        "### 🗑️ Removed",
        "### 🐛 Fixed",
        "### 🔒 Security",
    ]
    for heading in headings:
        assert heading in body

    positions = [body.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "### 📝 Other Changes" not in body


def test_build_markdown_links_the_changelog_range_when_a_compare_url_is_known() -> None:
    commits = [commit(C1, "feat: add login page").model_dump()]
    url = "https://git.local/PROJ/my-repo/compare/commits?sourceBranch=v1.1.0&targetBranch=v1.0.0"

    body = build_release_notes_markdown(
        commits,
        version="v1.1.0",
        previous_version="v1.0.0",
        compare_url=url,
    )

    assert f"**Full Changelog**: [v1.0.0...v1.1.0]({url})" in body
    assert "`v1.0.0...v1.1.0`" not in body


def test_build_markdown_keeps_the_range_plain_without_a_compare_url() -> None:
    commits = [commit(C1, "feat: add login page").model_dump()]

    body = build_release_notes_markdown(
        commits,
        version="v1.1.0",
        previous_version="v1.0.0",
        compare_url=None,
    )

    assert "**Full Changelog**: `v1.0.0...v1.1.0`" in body


def test_build_markdown_can_skip_authors_and_handles_empty_scopes() -> None:
    commits = [commit(C1, "feat: add login page").model_dump()]

    body = build_release_notes_markdown(commits, version="v1.1.0", include_authors=False)
    assert "by Jane Doe" not in body
    assert "Full Changelog" not in body

    empty = build_release_notes_markdown([], version="v1.0.0")
    assert "No commits found in this release scope" in empty


# --------------------------------------------------------------------------- #
# Author mentions and JIRA ticket links
# --------------------------------------------------------------------------- #


def test_author_reference_links_the_provider_account() -> None:
    linked = author_reference(
        {
            "author_name": "Aaron Liu",
            "author_username": "aaronpliu",
            "author_url": "https://git.local/users/aaronpliu",
        }
    )

    assert linked == " by [@aaronpliu](https://git.local/users/aaronpliu)"
    # a known account without a profile page is still mentioned as @login
    assert author_reference({"author_username": "aaronpliu"}) == " by @aaronpliu"
    # unknown account: the display name stays plain text
    assert author_reference({"author_name": "Jane Doe"}) == " by Jane Doe"
    assert author_reference({}) == ""


def test_build_markdown_mentions_the_author_account() -> None:
    commits = [
        {
            "id": "aaa1111",
            "display_id": "aaa1111",
            "message": "feat: add login page",
            "author_name": "Aaron Liu",
            "author_username": "aaronpliu",
            "author_url": "https://git.local/users/aaronpliu",
            "url": "https://git.local/commits/aaa1111",
        }
    ]

    body = build_release_notes_markdown(commits, version="v1.1.0")

    assert (
        "- add login page by [@aaronpliu](https://git.local/users/aaronpliu)"
        " in [aaa1111](https://git.local/commits/aaa1111)" in body
    )


def test_jira_settings_normalize_the_base_url_and_the_project_keys(monkeypatch) -> None:
    monkeypatch.setattr(settings, "JIRA_BASE_URL", "https://jira.local/")
    monkeypatch.setattr(settings, "JIRA_PROJECT_KEYS", "prl, ai")

    assert jira_settings() == ("https://jira.local", {"PRL", "AI"})

    monkeypatch.setattr(settings, "JIRA_BASE_URL", "")
    monkeypatch.setattr(settings, "JIRA_PROJECT_KEYS", "")

    assert jira_settings() == (None, set())


def test_linkify_jira_tickets_needs_a_base_url() -> None:
    assert linkify_jira_tickets("PRL-123 fix login") == "PRL-123 fix login"
    assert linkify_jira_tickets("PRL-123 fix login", base_url="") == "PRL-123 fix login"
    assert linkify_jira_tickets(None, base_url="https://jira.local") is None


def test_linkify_jira_tickets_links_the_keys() -> None:
    linked = linkify_jira_tickets("PRL-123 fix login, also PRL-456", base_url="https://jira.local")

    assert "[PRL-123](https://jira.local/browse/PRL-123)" in linked
    assert "[PRL-456](https://jira.local/browse/PRL-456)" in linked
    assert "fix login" in linked


def test_linkify_jira_tickets_can_be_restricted_to_project_keys() -> None:
    linked = linkify_jira_tickets(
        "PRL-123 fix login and UTF-8 encoding",
        base_url="https://jira.local",
        project_keys={"prl"},
    )

    assert "[PRL-123](https://jira.local/browse/PRL-123)" in linked
    # a look-alike key of another project stays plain text
    assert "UTF-8" in linked
    assert "[UTF-8]" not in linked


def test_build_markdown_links_the_ticket_keys_of_the_subject() -> None:
    commits = [commit(C1, "feat: add login page PRL-123").model_dump()]

    body = build_release_notes_markdown(
        commits,
        version="v1.1.0",
        jira_base_url="https://jira.local",
        jira_project_keys={"PRL"},
    )

    assert "- add login page [PRL-123](https://jira.local/browse/PRL-123)" in body


# --------------------------------------------------------------------------- #
# Service: CRUD
# --------------------------------------------------------------------------- #


async def test_create_draft_then_publish(db_session: AsyncSession) -> None:
    service = build_service(db_session)

    draft = await service.create_note(create_payload(), author="alice")
    assert draft.status == "draft"
    assert draft.published_date is None
    assert draft.name == "First release"

    published = await service.update_note(
        draft.id, ReleaseNoteUpdateRequest(status="published"), author="bob"
    )

    assert published is not None
    assert published.status == "published"
    assert published.published_date is not None
    assert published.author == "bob"


async def test_create_published_sets_the_publish_date_and_author(db_session: AsyncSession) -> None:
    service = build_service(db_session)

    note = await service.create_note(create_payload(status="published"), author="alice")

    assert note.published_date is not None
    assert note.author == "alice"


async def test_tag_defaults_to_the_name_and_defaults_name_to_the_tag(
    db_session: AsyncSession,
) -> None:
    service = build_service(db_session)

    note = await service.create_note(create_payload(tag_name=" v2.0.0 ", name=None))

    assert note.tag_name == "v2.0.0"
    assert note.name == "v2.0.0"


async def test_duplicate_tag_is_rejected(db_session: AsyncSession) -> None:
    service = build_service(db_session)
    await service.create_note(create_payload(), author="alice")

    with pytest.raises(ValueError, match="already exists"):
        await service.create_note(create_payload(name="Duplicate"), author="alice")


async def test_list_flags_the_latest_published_release(db_session: AsyncSession) -> None:
    service = build_service(db_session)

    await service.create_note(create_payload(tag_name="v1.0.0", status="published"))
    await service.create_note(
        create_payload(tag_name="v1.1.0", status="published", is_prerelease=True)
    )
    draft = await service.create_note(create_payload(tag_name="v1.2.0", status="draft"))
    latest_note = await service.create_note(create_payload(tag_name="v1.1.1", status="published"))

    notes, total = await service.list_notes(project_key="PROJ", repository_slug="my-repo")
    latest_id = await service.latest_published_id(project_key="PROJ", repository_slug="my-repo")

    assert total == 4
    assert {note.tag_name for note in notes} == {"v1.0.0", "v1.1.0", "v1.1.1", "v1.2.0"}
    # the draft is never "latest" and neither is the pre-release
    assert latest_id != draft.id
    assert latest_id == latest_note.id


async def test_list_filters_by_status_and_scopes_by_repository(db_session: AsyncSession) -> None:
    service = build_service(db_session)
    await service.create_note(create_payload(tag_name="v1.0.0", status="published"))
    await service.create_note(create_payload(tag_name="v1.1.0", status="draft"))
    await service.create_note(create_payload(repository_slug="other-repo", tag_name="v9.9.9"))

    published, published_total = await service.list_notes(
        project_key="PROJ", repository_slug="my-repo", status="published"
    )

    assert published_total == 1
    assert [note.tag_name for note in published] == ["v1.0.0"]


async def test_delete_removes_the_release(db_session: AsyncSession) -> None:
    service = build_service(db_session)
    note = await service.create_note(create_payload())

    assert await service.delete_note(note.id) is True
    assert await service.delete_note(note.id) is False
    assert await service.get_note(note.id) is None


async def test_update_missing_release_returns_none(db_session: AsyncSession) -> None:
    service = build_service(db_session)

    assert await service.update_note(4242, ReleaseNoteUpdateRequest(name="nope")) is None


async def test_author_avatars_only_returns_accounts_that_have_a_picture(
    db_session: AsyncSession,
) -> None:
    db_session.add_all(
        [
            AuthUser(
                username="alice",
                email="alice@example.com",
                password_hash="x",
                avatar_url="/api/v1/users/avatars/1_ab.png",
            ),
            AuthUser(
                username="bob",
                email="bob@example.com",
                password_hash="x",
                avatar_url=None,
            ),
        ]
    )
    await db_session.flush()

    service = build_service(db_session)
    avatars = await service.author_avatars(["alice", "bob", "octocat", None])

    # bob has no picture, octocat is a provider login without a local account
    assert avatars == {"alice": "/api/v1/users/avatars/1_ab.png"}
    assert await service.author_avatars([]) == {}
    assert await service.author_avatars([None]) == {}


def test_build_markdown_renders_the_summary_above_the_sections() -> None:
    commits = [commit(C1, "feat: add login page", author=None).model_dump()]

    body = build_release_notes_markdown(
        commits,
        version="v1.1.0",
        previous_version="v1.0.0",
        summary="This release adds single sign-on.",
    )

    assert body.splitlines()[0] == "## What's Changed"
    assert body.index("This release adds single sign-on.") < body.index("### ✨ Added")


def test_build_markdown_writes_the_sections_in_the_language_of_the_caller() -> None:
    commits = [commit(C1, "feat: add login page", author=None).model_dump()]

    body = build_release_notes_markdown(
        commits, version="v1.1.0", previous_version="v1.0.0", language="zh-CN"
    )

    assert body.startswith("## 变更内容")
    assert "### ✨ 新增" in body
    # an unknown language keeps the English it has always produced
    english = build_release_notes_markdown(commits, version="v1.1.0", language=None)
    assert english.startswith("## What's Changed")


def test_build_markdown_honours_a_caller_supplied_section() -> None:
    """A grouping decided elsewhere (an LLM's) wins over the commit subject."""
    payload = commit(C1, "wip").model_dump()
    payload["section"] = "Fixed"

    body = build_release_notes_markdown([payload], version="v1.1.0")

    assert "### 🐛 Fixed" in body
    assert "### 📝 Other Changes" not in body


def test_build_markdown_ignores_a_section_it_does_not_know() -> None:
    payload = commit(C1, "wip").model_dump()
    payload["section"] = "Features"

    body = build_release_notes_markdown([payload], version="v1.1.0")

    assert "### 📝 Other Changes" in body


def test_build_markdown_leaves_the_merges_out() -> None:
    """What a merge integrated is listed through the commits it merged."""
    commits = [
        commit(C1, "feat: add login page").model_dump(),
        commit(C2, "Merge pull request #42 from acme/feature/sso").model_dump(),
        commit(C3, "Merged in feature/sso (pull request #42)").model_dump(),
    ]

    body = build_release_notes_markdown(commits, version="v1.1.0")

    assert "add login page" in body
    assert "Merge" not in body
    assert "### 📝 Other Changes" not in body


def test_build_markdown_of_a_scope_that_holds_nothing_but_merges() -> None:
    """A release that only integrated work has no change of its own to list."""
    commits = [commit(C2, "Merge branch 'main' into feature/sso").model_dump()]

    body = build_release_notes_markdown(commits, version="v1.1.0")

    assert "Merge" not in body
    assert "### 📝 Other Changes" not in body
    assert "_No commits found in this release scope._" in body


# --------------------------------------------------------------------------- #
# Service: note generation
# --------------------------------------------------------------------------- #


async def test_preview_uses_the_compare_scope_when_a_previous_version_exists(
    db_session: AsyncSession,
) -> None:
    diff = StubDiffService([commit(C1, "feat: add login page")])
    service = build_service(db_session, diff)

    preview = await service.generate_preview(
        ReleaseNotePreviewRequest(
            project_key="PROJ",
            repository_slug="my-repo",
            version="v1.1.0",
            previous_version="v1.0.0",
        )
    )

    assert preview.commit_count == 1
    assert "add login page" in preview.body
    assert diff.compare_calls[0].source_ref == "v1.0.0"
    assert diff.compare_calls[0].target_ref == "v1.1.0"
    assert diff.list_calls == []


async def test_preview_lists_the_commits_the_release_adds_over_its_predecessor(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end against a mocked Bitbucket Server: a newer release adds work.

    Regression: the Server comparison used to answer ``previous \\ version``, so
    the notes of a release that contained its predecessor came out empty.
    """
    from urllib.parse import parse_qs, urlparse

    import httpx

    from src.services.git_providers import bitbucket_server
    from src.services.release_diff_service import ReleaseDiffService

    reachable = {"v1.0.0": [C1], "v1.1.0": [C1, C2]}

    def payload(sha: str) -> dict[str, Any]:
        return {
            "id": sha,
            "displayId": sha[:7],
            "author": {"name": "Jane Doe", "emailAddress": "jane@example.com"},
            "authorTimestamp": 1_690_000_000_000,
            "message": "feat: add login page" if sha == C2 else "chore: initial import",
        }

    def handler(request: httpx.Request) -> httpx.Response:
        query = parse_qs(urlparse(str(request.url)).query)
        # Bitbucket Server streams from \ to, i.e. git log to..from
        other = set(reachable[query["to"][0]])
        ids = [sha for sha in reachable[query["from"][0]] if sha not in other]
        values = [payload(sha) for sha in ids]
        return httpx.Response(200, json={"values": values, "size": len(values), "isLastPage": True})

    real_client = httpx.AsyncClient

    def client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("verify", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(bitbucket_server.httpx, "AsyncClient", client_factory)

    server_provider = bitbucket_server.BitbucketServerProvider()
    service = build_service(
        db_session,
        ReleaseDiffService(provider_factory=lambda _name: server_provider),
        provider=server_provider,  # type: ignore[arg-type]
    )

    preview = await service.generate_preview(
        ReleaseNotePreviewRequest(
            project_key="PROJ",
            repository_slug="my-repo",
            version="v1.1.0",
            previous_version="v1.0.0",
        )
    )

    assert preview.commit_count == 1
    assert [item["id"] for item in preview.commits] == [C2]
    assert "add login page" in preview.body
    assert "_No commits found in this release scope._" not in preview.body


async def test_preview_links_the_changelog_range_to_the_provider_comparison(
    db_session: AsyncSession,
) -> None:
    diff = StubDiffService([commit(C1, "feat: add login page")])
    provider = ComparingProvider()
    service = build_service(db_session, diff, provider=provider)

    preview = await service.generate_preview(
        ReleaseNotePreviewRequest(
            project_key="PROJ",
            repository_slug="my-repo",
            version="v1.1.0",
            previous_version="v1.0.0",
        )
    )

    # the range is asked for in the (base, target) order the providers expect
    assert provider.compare_url_calls == [("PROJ", "my-repo", "v1.0.0", "v1.1.0")]
    assert (
        "**Full Changelog**: [v1.0.0...v1.1.0]"
        "(https://github.local/PROJ/my-repo/compare/v1.0.0...v1.1.0)" in preview.body
    )


async def test_preview_addresses_the_cloud_workspace_in_the_comparison_link(
    db_session: AsyncSession,
) -> None:
    diff = StubDiffService([commit(C1, "feat: add login page")])
    provider = ComparingProvider(
        "https://bitbucket.org/aaronpliu/pylang/branches/compare/v1.1.0%0Dv1.0.0"
    )
    service = build_service(db_session, diff, provider=provider)

    preview = await service.generate_preview(
        ReleaseNotePreviewRequest(
            project_key="AI",
            repository_slug="pylang",
            workspace_slug="aaronpliu",
            git_provider="bitbucket_cloud",
            version="v1.1.0",
            previous_version="v1.0.0",
        )
    )

    # the business key stays AI, the workspace addresses the repository remotely
    assert provider.compare_url_calls == [("aaronpliu", "pylang", "v1.0.0", "v1.1.0")]
    assert "branches/compare/v1.1.0%0Dv1.0.0" in preview.body


async def test_preview_links_the_author_profile_and_the_jira_tickets(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "JIRA_BASE_URL", "https://jira.local")
    monkeypatch.setattr(settings, "JIRA_PROJECT_KEYS", "PRL")

    diff = StubDiffService(
        [
            CommitInfo(
                id=C1,
                display_id=C1[:7],
                author_name="Aaron Liu",
                author_username="aaronpliu",
                message="feat: add login page PRL-123",
            )
        ]
    )
    provider = ComparingProvider()
    service = build_service(db_session, diff, provider=provider)

    preview = await service.generate_preview(
        ReleaseNotePreviewRequest(
            project_key="PROJ",
            repository_slug="my-repo",
            version="v1.1.0",
            previous_version="v1.0.0",
        )
    )

    assert (
        "- add login page [PRL-123](https://jira.local/browse/PRL-123)"
        " by [@aaronpliu](https://github.local/aaronpliu)" in preview.body
    )
    # the resolved profile URL is exposed with the commits as well
    assert preview.commits[0]["author_url"] == "https://github.local/aaronpliu"


async def test_preview_keeps_the_plain_text_when_jira_is_not_configured(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "JIRA_BASE_URL", "")

    diff = StubDiffService([commit(C1, "feat: add login page PRL-123")])
    service = build_service(db_session, diff, provider=ComparingProvider())

    preview = await service.generate_preview(
        ReleaseNotePreviewRequest(
            project_key="PROJ",
            repository_slug="my-repo",
            version="v1.1.0",
            previous_version="v1.0.0",
        )
    )

    assert "PRL-123" in preview.body
    assert "browse/PRL-123" not in preview.body


async def test_preview_keeps_the_plain_range_when_no_comparison_url_exists(
    db_session: AsyncSession,
) -> None:
    diff = StubDiffService([commit(C1, "feat: add login page")])
    provider = ComparingProvider(url=None)
    service = build_service(db_session, diff, provider=provider)

    preview = await service.generate_preview(
        ReleaseNotePreviewRequest(
            project_key="PROJ",
            repository_slug="my-repo",
            version="v1.1.0",
            previous_version="v1.0.0",
        )
    )

    assert "**Full Changelog**: `v1.0.0...v1.1.0`" in preview.body


async def test_preview_survives_a_broken_comparison_link(db_session: AsyncSession) -> None:
    class ExplodingProvider(ComparingProvider):
        def web_compare_url(
            self, project_key: str, repository_slug: str, from_ref: str, to_ref: str
        ) -> str | None:
            raise RuntimeError("provider exploded")

    diff = StubDiffService([commit(C1, "feat: add login page")])
    service = build_service(db_session, diff, provider=ExplodingProvider())

    preview = await service.generate_preview(
        ReleaseNotePreviewRequest(
            project_key="PROJ",
            repository_slug="my-repo",
            version="v1.1.0",
            previous_version="v1.0.0",
        )
    )

    # a broken link must never fail the note generation
    assert preview.commit_count == 1
    assert "**Full Changelog**: `v1.0.0...v1.1.0`" in preview.body


async def test_preview_lists_commits_when_there_is_no_previous_version(
    db_session: AsyncSession,
) -> None:
    diff = StubDiffService([commit(C1, "feat: initial import")], truncated=True)
    provider = ComparingProvider()
    service = build_service(db_session, diff, provider=provider)

    preview = await service.generate_preview(
        ReleaseNotePreviewRequest(
            project_key="PROJ",
            repository_slug="my-repo",
            version="v1.0.0",
            workspace_slug="acme",
            git_provider="bitbucket_cloud",
        )
    )

    assert preview.commit_count == 1
    assert preview.truncated is True
    assert diff.compare_calls == []
    assert diff.list_calls[0]["ref"] == "v1.0.0"
    # a first release has nothing to compare against
    assert provider.compare_url_calls == []
    assert "Full Changelog" not in preview.body
    assert diff.list_calls[0]["workspace_slug"] == "acme"


async def test_preview_rejects_identical_versions() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ReleaseNotePreviewRequest(
            project_key="PROJ",
            repository_slug="my-repo",
            version="v1.0.0",
            previous_version="v1.0.0",
        )


# --------------------------------------------------------------------------- #
# Release scope resolution: the server answers "what came before this tag?"
# --------------------------------------------------------------------------- #


def tag_entry(name: str, sha: str, date: int | None = 100) -> dict[str, Any]:
    return {"name": name, "sha": sha, "date": date, "is_annotated": False}


def preview_request(**overrides: Any) -> ReleaseNotePreviewRequest:
    payload: dict[str, Any] = {
        "project_key": "PROJ",
        "repository_slug": "my-repo",
        "version": "v1.1.0",
    }
    payload.update(overrides)
    return ReleaseNotePreviewRequest(**payload)


async def test_preview_resolves_the_scope_from_the_repository_tags(
    db_session: AsyncSession,
) -> None:
    """No previous version supplied: the server resolves and verifies it."""
    diff = StubDiffService([commit(C2, "feat: add login")])
    provider = TagListingProvider(
        tags=[tag_entry("v1.0.0", C1), tag_entry("v1.1.0", C2, 200)],
        ancestors=(C1,),
    )
    service = build_service(db_session, diff, provider=provider)

    preview = await service.generate_preview(preview_request())

    assert preview.previous_version == "v1.0.0"
    assert preview.previous_sha == C1
    assert preview.version_sha == C2
    assert preview.previous_source == SOURCE_ANCESTOR
    assert preview.previous_verified is True
    assert preview.scope_reason == REASON_RESOLVED
    # the difference is asked with the resolved revisions, not with the tag names
    assert diff.compare_calls[0].source_ref == C1
    assert diff.compare_calls[0].target_ref == C2
    # the resolved scope reaches the generated body as well
    assert "Full Changelog" in preview.body


async def test_preview_labels_a_first_release(db_session: AsyncSession) -> None:
    """The oldest tag has no predecessor - the commits come from the history."""
    diff = StubDiffService([commit(C1, "feat: initial import")], truncated=True)
    provider = TagListingProvider(tags=[tag_entry("v1.0.0", C1)])
    service = build_service(db_session, diff, provider=provider)

    preview = await service.generate_preview(preview_request(version="v1.0.0"))

    assert preview.scope_reason == REASON_FIRST_RELEASE
    assert preview.previous_version is None
    assert preview.version_sha == C1
    assert diff.compare_calls == []
    assert diff.list_calls[0]["ref"] == "v1.0.0"


async def test_preview_reports_an_unresolvable_scope(db_session: AsyncSession) -> None:
    """A provider that cannot list tags degrades instead of failing the request."""
    diff = StubDiffService([commit(C1, "feat: initial import")])
    service = build_service(db_session, diff, provider=StubProvider())

    preview = await service.generate_preview(preview_request(version="v1.0.0"))

    assert preview.scope_reason == REASON_UNRESOLVED
    assert preview.previous_version is None
    assert preview.previous_source == SOURCE_NONE
    assert preview.previous_verified is False
    assert diff.compare_calls == []
    assert len(diff.list_calls) == 1


async def test_preview_keeps_a_supplied_previous_version(db_session: AsyncSession) -> None:
    """An explicit predecessor is authoritative - the resolver is not consulted."""
    diff = StubDiffService([commit(C1, "feat: add login")])
    scope = StubScopeService(ReleaseScope(version="v1.1.0", reason=REASON_UNRESOLVED))
    service = build_service(db_session, diff, scope=scope)

    preview = await service.generate_preview(preview_request(previous_version="v1.0.0"))

    assert preview.previous_version == "v1.0.0"
    assert preview.previous_source == SOURCE_EXPLICIT
    assert preview.previous_verified is True
    assert preview.scope_reason == REASON_PROVIDED
    assert scope.calls == []


async def test_preview_reports_an_inferred_scope_as_unverified(
    db_session: AsyncSession,
) -> None:
    """A scope resolved by tag order is used, but never presented as proven."""
    diff = StubDiffService([commit(C1, "feat: add login")])
    scope = StubScopeService(
        ReleaseScope(
            version="v1.1.0",
            previous_ref="v1.0.0",
            source=SOURCE_NAME_ORDER,
            verified=False,
            reason=REASON_RESOLVED,
        )
    )
    service = build_service(db_session, diff, scope=scope)

    preview = await service.generate_preview(preview_request())

    assert preview.previous_source == SOURCE_NAME_ORDER
    assert preview.previous_verified is False
    assert preview.scope_reason == REASON_RESOLVED


async def test_preview_passes_the_refresh_flag_to_the_resolver(
    db_session: AsyncSession,
) -> None:
    scope = StubScopeService(
        ReleaseScope(version="v1.1.0", previous_ref="v1.0.0", reason=REASON_RESOLVED)
    )
    service = build_service(db_session, StubDiffService([commit(C1, "feat")]), scope=scope)

    await service.generate_preview(preview_request(refresh=True))

    assert scope.calls[0]["refresh"] is True


async def test_preview_reports_the_scope_size_when_the_list_is_trimmed(
    db_session: AsyncSession,
) -> None:
    """The count is the scope, and the trimming is reported separately."""
    diff = StubDiffService([commit(C1, "feat: add login")], added_count=40)
    scope = StubScopeService(
        ReleaseScope(
            version="v1.1.0",
            previous_ref="v1.0.0",
            previous_sha=C1,
            source=SOURCE_ANCESTOR,
            verified=True,
            reason=REASON_RESOLVED,
        )
    )
    service = build_service(db_session, diff, scope=scope)

    preview = await service.generate_preview(preview_request())

    assert preview.commit_count == 40
    assert len(preview.commits) == 1
    assert preview.truncated is True


async def test_preview_flags_a_capped_scope_scan(db_session: AsyncSession) -> None:
    """A scan that hit its cap is reported, even when nothing was trimmed."""
    diff = StubDiffService([commit(C1, "feat: add login")], truncated=True)
    scope = StubScopeService(
        ReleaseScope(
            version="v1.1.0",
            previous_ref="v1.0.0",
            previous_sha=C1,
            source=SOURCE_ANCESTOR,
            verified=True,
            reason=REASON_RESOLVED,
        )
    )
    service = build_service(db_session, diff, scope=scope)

    preview = await service.generate_preview(preview_request())

    assert preview.commit_count == 1
    assert preview.truncated is True


# --------------------------------------------------------------------------- #
# Service: provider integration
# --------------------------------------------------------------------------- #


def test_parse_provider_datetime_handles_z_suffix_and_garbage() -> None:
    from datetime import datetime

    parsed = parse_provider_datetime("2026-09-01T10:00:00Z")
    assert isinstance(parsed, datetime)
    assert parsed.year == 2026
    assert parse_provider_datetime(None) is None
    assert parse_provider_datetime("not-a-date") is None


async def test_push_creates_the_provider_release(db_session: AsyncSession) -> None:
    provider = StubProvider()
    service = build_service(db_session, provider=provider)
    note = await service.create_note(create_payload(status="published"), author="alice")

    pushed = await service.push_to_provider(
        note.id,
        ReleaseNotePushRequest(
            project_key="PROJ",
            repository_slug="my-repo",
            git_provider="github_enterprise",
            target_commitish="main",
        ),
    )

    assert pushed is not None
    assert provider.created == [
        {
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "tag_name": "v1.0.0",
            "name": "First release",
            "body": "## What's Changed\n\n- initial",
            "target_commitish": "main",
            "draft": False,
            "prerelease": False,
        }
    ]
    assert pushed.external_provider == "github_enterprise"
    assert pushed.external_id == "1001"
    assert pushed.external_url.endswith("/releases/tag/v1.0.0")


async def test_push_updates_an_existing_provider_release(db_session: AsyncSession) -> None:
    provider = StubProvider()
    service = build_service(db_session, provider=provider)
    note = await service.create_note(create_payload(status="published"), author="alice")
    note.external_id = "1001"
    note.external_provider = "github_enterprise"
    await db_session.flush()

    await service.push_to_provider(
        note.id,
        ReleaseNotePushRequest(project_key="PROJ", repository_slug="my-repo"),
    )

    assert provider.created == []
    assert provider.updated == [
        {
            "release_id": "1001",
            "name": "First release",
            "body": "## What's Changed\n\n- initial",
            "prerelease": False,
        }
    ]


async def test_push_recreates_the_release_when_it_disappeared(db_session: AsyncSession) -> None:
    provider = StubProvider()
    provider.fail_update_with_not_found = True
    service = build_service(db_session, provider=provider)
    note = await service.create_note(create_payload(status="published"), author="alice")
    note.external_id = "1001"
    await db_session.flush()

    pushed = await service.push_to_provider(
        note.id,
        ReleaseNotePushRequest(project_key="PROJ", repository_slug="my-repo"),
    )

    assert len(provider.created) == 1
    assert pushed is not None
    assert pushed.external_id == "1001"


async def test_push_rejects_providers_without_release_support(db_session: AsyncSession) -> None:
    service = build_service(db_session, provider=StubProvider(supports_releases=False))
    note = await service.create_note(create_payload(status="published"))

    with pytest.raises(ValueError, match="does not support releases"):
        await service.push_to_provider(
            note.id, ReleaseNotePushRequest(project_key="PROJ", repository_slug="my-repo")
        )


async def test_push_returns_none_for_unknown_release(db_session: AsyncSession) -> None:
    service = build_service(db_session, provider=StubProvider())

    pushed = await service.push_to_provider(
        4242, ReleaseNotePushRequest(project_key="PROJ", repository_slug="my-repo")
    )

    assert pushed is None


async def test_import_creates_published_releases_and_skips_existing(
    db_session: AsyncSession,
) -> None:
    provider = StubProvider()
    provider.releases = [
        {
            "id": "9001",
            "tag_name": "v1.0.0",
            "name": "v1.0.0",
            "body": "first",
            "draft": False,
            "prerelease": False,
            "html_url": "https://github.local/PROJ/my-repo/releases/tag/v1.0.0",
            "published_at": "2026-08-01T10:00:00Z",
            "author": "octocat",
        },
        {
            "id": "9002",
            "tag_name": "v1.1.0-rc1",
            "name": "v1.1.0-rc1",
            "body": "rc",
            "draft": False,
            "prerelease": True,
            "html_url": "https://github.local/PROJ/my-repo/releases/tag/v1.1.0-rc1",
            "published_at": "2026-09-01T10:00:00Z",
            "author": "octocat",
        },
        {
            "id": "9003",
            "tag_name": "v1.2.0",
            "name": "upcoming",
            "body": "draft on the provider",
            "draft": True,
            "prerelease": False,
            "html_url": "https://github.local/PROJ/my-repo/releases/tag/v1.2.0",
            "published_at": None,
            "author": "octocat",
        },
    ]
    service = build_service(db_session, provider=provider)
    await service.create_note(create_payload(tag_name="v1.0.0", status="published"))

    imported, updated, skipped, items = await service.import_from_provider(
        ReleaseNoteImportRequest(project_key="PROJ", repository_slug="my-repo")
    )

    assert (imported, updated, skipped) == (2, 0, 1)
    assert {note.tag_name for note in items} == {"v1.1.0-rc1", "v1.2.0"}

    prerelease = await service.get_note_by_tag(
        project_key="PROJ", repository_slug="my-repo", tag_name="v1.1.0-rc1"
    )
    assert prerelease is not None
    assert prerelease.is_prerelease is True
    assert prerelease.status == "published"
    assert prerelease.author == "octocat"
    assert prerelease.external_url.endswith("/releases/tag/v1.1.0-rc1")

    draft = await service.get_note_by_tag(
        project_key="PROJ", repository_slug="my-repo", tag_name="v1.2.0"
    )
    assert draft is not None
    assert draft.status == "draft"


async def test_import_overwrites_existing_releases_on_demand(db_session: AsyncSession) -> None:
    provider = StubProvider()
    provider.releases = [
        {
            "id": "9001",
            "tag_name": "v1.0.0",
            "name": "Provider title",
            "body": "provider notes",
            "draft": False,
            "prerelease": False,
            "html_url": "https://github.local/PROJ/my-repo/releases/tag/v1.0.0",
            "published_at": "2026-08-01T10:00:00Z",
            "author": "octocat",
        }
    ]
    service = build_service(db_session, provider=provider)
    await service.create_note(create_payload(tag_name="v1.0.0", status="draft"))

    imported, updated, skipped, _ = await service.import_from_provider(
        ReleaseNoteImportRequest(project_key="PROJ", repository_slug="my-repo", overwrite=True)
    )

    assert (imported, updated, skipped) == (0, 1, 0)
    refreshed = await service.get_note_by_tag(
        project_key="PROJ", repository_slug="my-repo", tag_name="v1.0.0"
    )
    assert refreshed is not None
    assert refreshed.name == "Provider title"
    assert refreshed.body == "provider notes"
    assert refreshed.status == "published"


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@pytest.fixture
def authenticated_client(db_session):
    """Test client with auth + release note service dependencies overridden."""

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    async def _db_session():
        yield db_session

    rbac = StubRBAC()
    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = _db_session
    app.dependency_overrides[get_release_note_service] = lambda: build_service(db_session)
    app.dependency_overrides[get_rbac_service] = lambda: rbac
    yield rbac
    app.dependency_overrides.pop(get_current_user_with_token, None)
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_release_note_service, None)
    app.dependency_overrides.pop(get_rbac_service, None)


async def test_endpoint_checks_rbac_permissions(
    async_client, authenticated_client, db_session
) -> None:
    rbac: StubRBAC = authenticated_client
    rbac.allowed = False

    denied = await async_client.get(
        "/api/v1/release/notes", params={"project_key": "PROJ", "repository_slug": "my-repo"}
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "FORBIDDEN"

    rbac.allowed = True
    allowed = await async_client.get(
        "/api/v1/release/notes", params={"project_key": "PROJ", "repository_slug": "my-repo"}
    )
    assert allowed.status_code == 200

    # read for listings, manage for mutations
    assert [check["action"] for check in rbac.checks] == ["read", "read"]


async def test_endpoint_requires_manage_permission_for_writes(
    async_client, authenticated_client
) -> None:
    rbac: StubRBAC = authenticated_client
    rbac.allowed = False

    created = await async_client.post(
        "/api/v1/release/notes",
        json={"project_key": "PROJ", "repository_slug": "my-repo", "tag_name": "v9.9.9"},
    )

    assert created.status_code == 403
    assert rbac.checks[0]["action"] == "manage"
    assert rbac.checks[0]["resource_type"] == "release_note"


async def test_endpoint_create_list_and_publish(async_client, authenticated_client) -> None:
    created = await async_client.post(
        "/api/v1/release/notes",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "tag_name": "v1.0.0",
            "name": "First release",
            "body": "notes",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "draft"
    assert body["is_latest"] is False
    note_id = body["id"]

    published = await async_client.put(
        f"/api/v1/release/notes/{note_id}", json={"status": "published"}
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["is_latest"] is True

    listed = await async_client.get(
        "/api/v1/release/notes", params={"project_key": "PROJ", "repository_slug": "my-repo"}
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["is_latest"] is True


async def test_endpoint_returns_the_author_avatar_url(
    async_client, authenticated_client, db_session
) -> None:
    db_session.add(
        AuthUser(
            username="tester",
            email="tester@example.com",
            password_hash="x",
            avatar_url="/api/v1/users/avatars/1_ab.png",
        )
    )
    await db_session.flush()

    created = await async_client.post(
        "/api/v1/release/notes",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "tag_name": "v1.0.0",
            "status": "published",
        },
    )

    assert created.status_code == 201
    assert created.json()["author"] == "tester"
    assert created.json()["author_avatar_url"] == "/api/v1/users/avatars/1_ab.png"

    listed = await async_client.get(
        "/api/v1/release/notes", params={"project_key": "PROJ", "repository_slug": "my-repo"}
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["author_avatar_url"] == "/api/v1/users/avatars/1_ab.png"


async def test_endpoint_leaves_the_avatar_empty_without_a_local_account(
    async_client, authenticated_client
) -> None:
    created = await async_client.post(
        "/api/v1/release/notes",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "tag_name": "v1.0.0",
            "status": "published",
        },
    )

    assert created.status_code == 201
    assert created.json()["author_avatar_url"] is None


async def test_endpoint_rejects_duplicate_tag(async_client, authenticated_client) -> None:
    payload = {
        "project_key": "PROJ",
        "repository_slug": "my-repo",
        "tag_name": "v2.0.0",
    }
    assert (await async_client.post("/api/v1/release/notes", json=payload)).status_code == 201

    duplicate = await async_client.post("/api/v1/release/notes", json=payload)

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["error"] == "CONFLICT"


async def test_endpoint_404s_and_status_validation(async_client, authenticated_client) -> None:
    missing = await async_client.get("/api/v1/release/notes/9999")
    assert missing.status_code == 404

    bad_status = await async_client.get(
        "/api/v1/release/notes",
        params={"project_key": "PROJ", "repository_slug": "my-repo", "status": "nope"},
    )
    assert bad_status.status_code == 422


async def test_endpoint_pushes_and_imports_through_the_provider(
    async_client, authenticated_client, db_session
) -> None:
    provider = StubProvider()
    provider.releases = [
        {
            "id": "9001",
            "tag_name": "v2.0.0",
            "name": "v2.0.0",
            "body": "imported",
            "draft": False,
            "prerelease": False,
            "html_url": "https://github.local/PROJ/my-repo/releases/tag/v2.0.0",
            "published_at": "2026-09-20T10:00:00Z",
            "author": "octocat",
        }
    ]
    app.dependency_overrides[get_release_note_service] = lambda: build_service(
        db_session, provider=provider
    )

    created = await async_client.post(
        "/api/v1/release/notes",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "tag_name": "v1.0.0",
            "name": "First release",
            "status": "published",
        },
    )
    assert created.status_code == 201
    note_id = created.json()["id"]

    pushed = await async_client.post(
        f"/api/v1/release/notes/{note_id}/push",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "git_provider": "github_enterprise",
            "target_commitish": "main",
        },
    )
    assert pushed.status_code == 200
    assert pushed.json()["external_provider"] == "github_enterprise"
    assert pushed.json()["external_url"].endswith("/releases/tag/v1.0.0")
    assert provider.created[0]["target_commitish"] == "main"

    imported = await async_client.post(
        "/api/v1/release/notes/import",
        json={"project_key": "PROJ", "repository_slug": "my-repo", "limit": 10},
    )
    assert imported.status_code == 200
    body = imported.json()
    assert body["imported"] == 1
    assert body["skipped"] == 0  # the provider only had v2.0.0
    assert [item["tag_name"] for item in body["items"]] == ["v2.0.0"]


async def test_endpoint_push_reports_unsupported_provider(
    async_client, authenticated_client, db_session
) -> None:
    app.dependency_overrides[get_release_note_service] = lambda: build_service(
        db_session, provider=StubProvider(supports_releases=False)
    )
    created = await async_client.post(
        "/api/v1/release/notes",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "tag_name": "v3.0.0",
            "status": "published",
        },
    )
    note_id = created.json()["id"]

    pushed = await async_client.post(
        f"/api/v1/release/notes/{note_id}/push",
        json={"project_key": "PROJ", "repository_slug": "my-repo"},
    )

    assert pushed.status_code == 400
    assert "does not support releases" in pushed.json()["detail"]["message"]


async def test_endpoint_requires_authentication(async_client) -> None:
    async def _db_session() -> None:
        return None  # 401 is raised before any query runs

    app.dependency_overrides[get_db_session] = _db_session
    try:
        response = await async_client.get(
            "/api/v1/release/notes", params={"project_key": "PROJ", "repository_slug": "my-repo"}
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 401
