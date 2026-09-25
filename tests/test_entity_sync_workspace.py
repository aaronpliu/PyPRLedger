"""Tests for workspace-based routing of entity sync (Bitbucket Cloud).

No HTTP traffic: the git provider is replaced by a recording stub so the
identifiers used to address projects and repositories can be asserted.
"""

from __future__ import annotations

from typing import Any

import pytest

import src.services.entity_sync_service as entity_sync_module
from src.services.entity_sync_service import EntitySyncService


class RecordingProvider:
    """Stub provider that records the identifiers it was called with."""

    def __init__(self, name: str) -> None:
        self._name = name
        self.project_lookups: list[str] = []
        self.repository_lookups: list[tuple[str, str]] = []

    @property
    def name(self) -> str:
        return self._name

    async def get_project_info(self, project_key: str) -> dict[str, Any]:
        self.project_lookups.append(project_key)
        return {
            "project_id": 1,
            "project_name": project_key,
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
    assert repository.repository_slug == "pylang"


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
