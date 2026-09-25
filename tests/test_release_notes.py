"""Tests for release notes (version releases).

The git provider is never contacted: the note generator is wired to a stub diff
service and the CRUD tests use the in-memory SQLite fixture.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.endpoints.release_notes import get_rbac_service, get_release_note_service
from src.core.database import get_db_session
from src.core.exceptions import NotFoundException
from src.core.git_provider import GitProvider
from src.core.permissions import get_current_user_with_token
from src.main import app
from src.models.auth_user import AuthUser
from src.schemas.release_diff import CommitInfo
from src.schemas.release_note import (
    ReleaseNoteCreateRequest,
    ReleaseNoteImportRequest,
    ReleaseNotePreviewRequest,
    ReleaseNotePushRequest,
    ReleaseNoteUpdateRequest,
)
from src.services.git_providers.base import BaseGitProvider
from src.services.release_note_service import (
    ReleaseNoteService,
    build_release_notes_markdown,
    commit_section,
    commit_subject,
    parse_provider_datetime,
)


C1 = "1111111111111111111111111111111111111111"
C2 = "2222222222222222222222222222222222222222"
C3 = "3333333333333333333333333333333333333333"


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

    def __init__(self, added: list[CommitInfo] | None = None, truncated: bool = False) -> None:
        self._added = added or []
        self._truncated = truncated
        self.compare_calls: list[Any] = []
        self.list_calls: list[dict[str, Any]] = []

    async def compare_releases(self, request: Any) -> Any:
        self.compare_calls.append(request)
        return type(
            "Comparison",
            (),
            {"added_commits": self._added, "truncated": self._truncated},
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
) -> ReleaseNoteService:
    stub = provider or StubProvider()
    return ReleaseNoteService(
        db,
        diff_service=diff or StubDiffService(),  # type: ignore[arg-type]
        provider_factory=lambda _name: stub,
    )


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


def test_commit_section_maps_conventional_types() -> None:
    assert commit_section("feat(api): add endpoint") == "Features"
    assert commit_section("fix: crash") == "Bug Fixes"
    assert commit_section("perf!: faster") == "Performance"
    assert commit_section("chore: bump deps") == "Maintenance"
    assert commit_section("random change") == "Other Changes"
    assert commit_section(None) == "Other Changes"


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
    assert "### 🚀 Features" in body
    assert "### 🐛 Bug Fixes" in body
    assert "### 📚 Documentation" in body
    assert "- add login page by Jane Doe in [1111111](https://git.local/commits/1111111)" in body
    assert "- crash on logout by John Roe in [2222222](https://git.local/commits/2222222)" in body
    # section order: features before bug fixes
    assert body.index("Features") < body.index("Bug Fixes")
    assert "**Full Changelog**: `v1.0.0...v1.1.0`" in body


def test_build_markdown_can_skip_authors_and_handles_empty_scopes() -> None:
    commits = [commit(C1, "feat: add login page").model_dump()]

    body = build_release_notes_markdown(commits, version="v1.1.0", include_authors=False)
    assert "by Jane Doe" not in body
    assert "Full Changelog" not in body

    empty = build_release_notes_markdown([], version="v1.0.0")
    assert "No commits found in this release scope" in empty


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
    assert diff.compare_calls[0].old_release_ref == "v1.0.0"
    assert diff.compare_calls[0].new_release_ref == "v1.1.0"
    assert diff.list_calls == []


async def test_preview_lists_commits_when_there_is_no_previous_version(
    db_session: AsyncSession,
) -> None:
    diff = StubDiffService([commit(C1, "feat: initial import")], truncated=True)
    service = build_service(db_session, diff)

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
