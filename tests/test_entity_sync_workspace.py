"""Tests for workspace-based routing of entity sync (Bitbucket Cloud).

No HTTP traffic: the git provider is replaced by a recording stub so the
identifiers used to address projects and repositories can be asserted.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

import src.services.entity_sync_service as entity_sync_module
from src.models.project import Project
from src.models.repository import Repository
from src.models.user import User
from src.services.entity_sync_service import EntitySyncService


class RecordingProvider:
    """Stub provider that records the identifiers it was called with."""

    def __init__(self, name: str) -> None:
        self._name = name
        self.project_lookups: list[str] = []
        self.repository_lookups: list[tuple[str, str]] = []
        self.user_lookups: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    async def get_project_info(self, project_key: str) -> dict[str, Any]:
        self.project_lookups.append(project_key)
        return {
            "project_id": 1,
            "project_name": f"{project_key} workspace",
            "project_key": project_key,
            "project_url": f"https://example.com/{project_key}",
        }

    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict[str, Any]:
        self.repository_lookups.append((workspace, repo_slug))
        return {
            "repository_id": 2,
            "repository_name": repo_slug,
            "repository_slug": repo_slug,
            "repository_url": f"https://example.com/{workspace}/{repo_slug}",
        }

    async def get_user_info(self, username: str) -> dict[str, Any]:
        self.user_lookups.append(username)
        # one and the same remote account, whatever login it is addressed with
        return {
            "user_id": 7,
            "username": username,
            "display_name": username.title(),
            "email_address": "alice@example.com",
        }


def install_provider(monkeypatch, name: str) -> RecordingProvider:
    provider = RecordingProvider(name)
    monkeypatch.setattr(entity_sync_module, "get_git_provider", lambda *_: provider)
    return provider


async def test_cloud_uses_workspace_slug_for_remote_lookups(db_session, monkeypatch) -> None:
    provider = install_provider(monkeypatch, "bitbucket_cloud")

    service = EntitySyncService(
        db_session, git_provider="bitbucket_cloud", workspace_slug="aaronpliu"
    )
    project = await service.sync_project("AI")
    repository = await service.sync_repository("pylang", project)

    # Remote calls address the workspace, the database keeps the business key.
    assert provider.project_lookups == ["aaronpliu"]
    assert provider.repository_lookups == [("aaronpliu", "pylang")]
    assert project.project_key == "AI"
    assert project.project_name == "AI"
    assert repository.repository_slug == "pylang"


async def test_cloud_keeps_workspace_name_without_alias(db_session, monkeypatch) -> None:
    install_provider(monkeypatch, "bitbucket_cloud")

    project = await EntitySyncService(db_session, git_provider="bitbucket_cloud").sync_project(
        "aaronpliu"
    )

    assert project.project_name == "aaronpliu workspace"


async def test_server_keeps_remote_project_name(db_session, monkeypatch) -> None:
    install_provider(monkeypatch, "bitbucket_server")

    project = await EntitySyncService(
        db_session, git_provider="bitbucket_server", workspace_slug="aaronpliu"
    ).sync_project("AI")

    assert project.project_name == "AI workspace"


async def test_cloud_without_workspace_slug_falls_back_to_project_key(
    db_session, monkeypatch
) -> None:
    provider = install_provider(monkeypatch, "bitbucket_cloud")

    service = EntitySyncService(db_session, git_provider="bitbucket_cloud")
    project = await service.sync_project("aaronpliu")
    await service.sync_repository("pylang", project)

    assert provider.project_lookups == ["aaronpliu"]
    assert provider.repository_lookups == [("aaronpliu", "pylang")]


async def test_workspace_slug_is_ignored_for_server(db_session, monkeypatch) -> None:
    provider = install_provider(monkeypatch, "bitbucket_server")

    service = EntitySyncService(
        db_session, git_provider="bitbucket_server", workspace_slug="aaronpliu"
    )
    project = await service.sync_project("AI")
    await service.sync_repository("pylang", project)

    assert provider.project_lookups == ["AI"]
    assert provider.repository_lookups == [("AI", "pylang")]


async def test_blank_workspace_slug_falls_back_to_project_key(db_session, monkeypatch) -> None:
    provider = install_provider(monkeypatch, "bitbucket_cloud")

    service = EntitySyncService(db_session, git_provider="bitbucket_cloud", workspace_slug="   ")
    project = await service.sync_project("AI")
    await service.sync_repository("pylang", project)

    assert provider.project_lookups == ["AI"]
    assert provider.repository_lookups == [("AI", "pylang")]


async def test_same_remote_project_is_reused_across_business_keys(db_session, monkeypatch) -> None:
    """One remote project must never be inserted twice.

    ``project.project_id`` is unique while the business key (project_key /
    workspace_slug) can address the same workspace in different ways - inserting
    again used to fail with "Duplicate entry ... for key 'project.project_id'"
    (issue seen on POST /api/v1/reviews).
    """
    install_provider(monkeypatch, "bitbucket_cloud")

    first = await EntitySyncService(
        db_session, git_provider="bitbucket_cloud", workspace_slug="aaronpliu"
    ).sync_project("AI")

    # the very same workspace, addressed with another business key
    second = await EntitySyncService(
        db_session, git_provider="bitbucket_cloud", workspace_slug="aaronpliu"
    ).sync_project("web-development")

    assert second.project_id == first.project_id
    # the already stored business key wins
    assert second.project_key == "AI"

    rows = (await db_session.execute(select(Project))).scalars().all()
    assert len(rows) == 1


async def test_concurrently_inserted_remote_project_is_reused(db_session, monkeypatch) -> None:
    """A race between the lookup and the insert must not poison the transaction.

    The insert runs inside a savepoint, so the duplicate key only rolls that back
    and the row stored by the other request is reused.
    """
    provider = install_provider(monkeypatch, "bitbucket_cloud")
    real_lookup = EntitySyncService._find_project_by_remote
    lookup_calls = 0

    async def racing_lookup(self, current_provider, project_info):
        nonlocal lookup_calls
        stored = await real_lookup(self, current_provider, project_info)
        if stored is None and lookup_calls == 0:
            lookup_calls += 1
            # a concurrent request stores the same remote project right after our lookup
            self.db.add(
                Project(
                    project_id=project_info["project_id"],
                    project_name="racer",
                    project_key="RACER",
                    project_url="https://bitbucket.org/aaronpliu/",
                    git_provider="bitbucket_cloud",
                )
            )
            await self.db.flush()
        return stored

    monkeypatch.setattr(EntitySyncService, "_find_project_by_remote", racing_lookup)

    project = await EntitySyncService(
        db_session, git_provider="bitbucket_cloud", workspace_slug="aaronpliu"
    ).sync_project("AI")

    assert provider.project_lookups == ["aaronpliu"]
    # the row of the other request wins, no duplicate key error is raised
    assert project.project_key == "RACER"

    rows = (await db_session.execute(select(Project))).scalars().all()
    assert len(rows) == 1


async def test_same_remote_repository_is_reused_across_slugs(db_session, monkeypatch) -> None:
    install_provider(monkeypatch, "bitbucket_server")

    service = EntitySyncService(db_session, git_provider="bitbucket_server")
    project = await service.sync_project("PROJ")

    first = await service.sync_repository("alpha-api", project)
    # same remote repository (repository_id 2), reached through another slug
    second = await service.sync_repository("alpha-api-renamed", project)

    assert second.repository_id == first.repository_id
    assert second.repository_slug == "alpha-api"

    rows = (await db_session.execute(select(Repository))).scalars().all()
    assert len(rows) == 1


async def test_same_remote_user_is_reused_across_logins(db_session, monkeypatch) -> None:
    install_provider(monkeypatch, "bitbucket_server")

    service = EntitySyncService(db_session, git_provider="bitbucket_server")

    first = await service.sync_user("alice")
    second = await service.sync_user("alice.renamed")

    assert second.user_id == first.user_id
    assert second.username == "alice"

    rows = (await db_session.execute(select(User))).scalars().all()
    assert len(rows) == 1


def test_review_create_accepts_workspace_slug() -> None:
    from src.schemas.pull_request import ReviewCreate

    payload = ReviewCreate(
        pull_request_id="42",
        project_key="AI",
        repository_slug="pylang",
        source_branch="feature/Pylang",
        target_branch="main",
        git_provider="bitbucket_cloud",
        workspace_slug="aaronpliu",
    )

    assert payload.workspace_slug == "aaronpliu"


@pytest.mark.parametrize("value", ["", "x" * 129])
def test_review_create_rejects_invalid_workspace_slug(value: str) -> None:
    from pydantic import ValidationError

    from src.schemas.pull_request import ReviewCreate

    with pytest.raises(ValidationError):
        ReviewCreate(
            pull_request_id="42",
            project_key="AI",
            repository_slug="pylang",
            source_branch="feature/Pylang",
            target_branch="main",
            workspace_slug=value,
        )
