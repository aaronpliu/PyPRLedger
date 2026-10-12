"""Tests for where each repository publishes its releases.

A release is published per repository, so the space and the parent page resolve in
three tiers: the repository, then its project, then the instance. What is pinned
here is that fallback - each field on its own, since a space is usually set once
per project and a parent page per repository - along with the settings endpoint
that reads and writes it.

The permission gate is opened in the fixture below: `require_permission` is shared
by every settings endpoint, and what is under test is the shape of a target. The
settings store underneath stays the real one, so the round trip is a genuine read
and write.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.endpoints.rbac import get_rbac_service
from src.core.config import settings
from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.main import app
from src.models.auth_user import AuthUser
from src.services.confluence.targets import (
    MAX_TARGETS,
    SETTING_KEY,
    empty_targets,
    normalize_targets,
    parse_stored_targets,
    resolve,
)
from src.services.project_registry_service import ProjectRegistryService
from src.services.rbac_service import RBACService


TARGETS_URL = "/api/v1/rbac/settings/confluence"


@pytest.fixture
def instance_defaults_set(monkeypatch):
    """An instance whose environment supplies all three defaults."""
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SPACE_KEY", "DOC")
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_PARENT_PAGE_ID", "100")
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SYNC_ENABLED", True)


# --------------------------------------------------------------------------- #
# The fallback itself
# --------------------------------------------------------------------------- #


def test_an_unconfigured_repository_gets_the_instance_default(instance_defaults_set) -> None:
    resolution = resolve(empty_targets(), "PROJ", "my-repo")

    assert resolution.space_key == "DOC"
    assert resolution.parent_page_id == "100"
    assert resolution.enabled is True
    assert resolution.space_source == "instance"
    assert resolution.configured is False
    assert resolution.has_space is True


def test_each_field_falls_back_on_its_own(instance_defaults_set) -> None:
    """The arrangement this is built for: a space per project, a page per repository."""
    config = normalize_targets(
        {
            "projects": [{"project_key": "PROJ", "space_key": "PROJSPACE"}],
            "repositories": [
                {"project_key": "PROJ", "repository_slug": "my-repo", "parent_page_id": "555"}
            ],
        }
    )

    resolution = resolve(config, "PROJ", "my-repo")

    assert (resolution.space_key, resolution.space_source) == ("PROJSPACE", "project")
    assert (resolution.parent_page_id, resolution.parent_source) == ("555", "repository")
    # The switch nobody mentioned is still the instance's to decide.
    assert resolution.enabled_source == "instance"


def test_a_repository_target_wins_over_its_project(instance_defaults_set) -> None:
    config = normalize_targets(
        {
            "projects": [{"project_key": "PROJ", "space_key": "PROJSPACE", "parent_page_id": "1"}],
            "repositories": [
                {
                    "project_key": "PROJ",
                    "repository_slug": "my-repo",
                    "space_key": "OWNSPACE",
                    "parent_page_id": "2",
                }
            ],
        }
    )

    resolution = resolve(config, "PROJ", "my-repo")

    assert (resolution.space_key, resolution.space_source) == ("OWNSPACE", "repository")
    assert (resolution.parent_page_id, resolution.parent_source) == ("2", "repository")


def test_a_project_target_does_not_reach_another_project(instance_defaults_set) -> None:
    config = normalize_targets({"projects": [{"project_key": "OTHER", "space_key": "OTHER"}]})

    resolution = resolve(config, "PROJ", "my-repo")

    assert resolution.space_key == "DOC"
    assert resolution.space_source == "instance"
    assert resolution.configured is False


def test_a_repository_can_be_switched_off_without_saying_where_it_goes(
    instance_defaults_set,
) -> None:
    """An internal library publishes nowhere, and that is a decision of its own."""
    config = normalize_targets(
        {
            "repositories": [
                {"project_key": "PROJ", "repository_slug": "internal-lib", "enabled": False}
            ]
        }
    )

    resolution = resolve(config, "PROJ", "internal-lib")

    assert resolution.enabled is False
    assert resolution.enabled_source == "repository"
    assert resolution.configured is True


def test_one_repository_being_off_leaves_its_neighbours_alone(instance_defaults_set) -> None:
    config = normalize_targets(
        {
            "projects": [{"project_key": "PROJ", "space_key": "PROJSPACE"}],
            "repositories": [
                {"project_key": "PROJ", "repository_slug": "internal-lib", "enabled": False}
            ],
        }
    )

    assert resolve(config, "PROJ", "internal-lib").enabled is False
    assert resolve(config, "PROJ", "my-repo").enabled is True
    assert resolve(config, "PROJ", "my-repo").space_key == "PROJSPACE"


def test_a_repository_can_turn_publishing_back_on_where_its_project_is_off() -> None:
    """Publishing is a decision of its own, and the narrower level still wins."""
    config = normalize_targets(
        {
            "projects": [{"project_key": "PROJ", "space_key": "PROJSPACE", "enabled": False}],
            "repositories": [
                {"project_key": "PROJ", "repository_slug": "my-repo", "enabled": True}
            ],
        }
    )

    assert resolve(config, "PROJ", "my-repo").enabled is True
    assert resolve(config, "PROJ", "other-repo").enabled is False


def test_the_environment_switch_is_not_what_decides_publishing(monkeypatch) -> None:
    """It is the default of the automatic path, and nothing else.

    An instance that syncs nothing by itself is still an instance whose releases can
    be written to Confluence deliberately.
    """
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SYNC_ENABLED", False)
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SPACE_KEY", "DOC")

    resolution = resolve(empty_targets(), "PROJ", "my-repo")

    assert (resolution.enabled, resolution.enabled_source) == (True, "instance")
    assert (resolution.auto_sync, resolution.auto_sync_source) == (False, "instance")


def test_a_repository_can_be_left_out_of_the_automatic_sync(instance_defaults_set) -> None:
    """The other half of the split: published, but never by itself."""
    config = normalize_targets(
        {
            "projects": [{"project_key": "PROJ", "space_key": "PROJSPACE"}],
            "repositories": [
                {"project_key": "PROJ", "repository_slug": "my-repo", "auto_sync": False}
            ],
        }
    )

    resolution = resolve(config, "PROJ", "my-repo")

    assert resolution.enabled is True
    assert (resolution.auto_sync, resolution.auto_sync_source) == (False, "repository")
    # Its sibling is untouched: one repository opting out is its own decision.
    assert resolve(config, "PROJ", "other-repo").auto_sync is True


def test_the_environment_switch_is_a_ceiling_over_the_automatic_path(monkeypatch) -> None:
    """A level below may switch the automatic path off, never on."""
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SYNC_ENABLED", False)
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SPACE_KEY", "DOC")
    config = normalize_targets(
        {"repositories": [{"project_key": "PROJ", "repository_slug": "my-repo", "auto_sync": True}]}
    )

    resolution = resolve(config, "PROJ", "my-repo")

    assert resolution.auto_sync is False
    # Reported as the instance's decision, because that is what answered it.
    assert resolution.auto_sync_source == "instance"
    # And publishing is unaffected by it.
    assert resolution.enabled is True


def test_a_repository_with_no_space_anywhere_has_none(monkeypatch) -> None:
    """The instance may have no space of its own: the space is asked of the tiers."""
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SYNC_ENABLED", True)
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SPACE_KEY", None)
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_PARENT_PAGE_ID", None)

    resolution = resolve(empty_targets(), "PROJ", "my-repo")

    assert resolution.has_space is False
    assert resolution.parent_page_id == ""


# --------------------------------------------------------------------------- #
# What a target may say
# --------------------------------------------------------------------------- #


def test_a_target_that_decides_nothing_is_refused() -> None:
    """Empty fields mean "not here", so a target empty in every field says nothing."""
    with pytest.raises(ValueError, match="space key, a parent page id, or switch"):
        normalize_targets({"projects": [{"project_key": "PROJ"}]})


def test_a_target_may_say_only_that_it_does_not_sync_by_itself() -> None:
    """Switching the automatic path off is deciding something, so it stands alone."""
    config = normalize_targets(
        {
            "repositories": [
                {"project_key": "PROJ", "repository_slug": "my-repo", "auto_sync": False}
            ]
        }
    )

    assert config["repositories"][0]["auto_sync"] is False
    assert config["repositories"][0]["enabled"] is None


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({"space_key": "DOC"}, "needs a project key"),
        ({"project_key": "PROJ", "space_key": "TWO WORDS"}, "cannot contain spaces"),
        ({"project_key": "PROJ", "parent_page_id": "page-1"}, "is a number"),
        ({"project_key": "PROJ", "parent_page_id": "9" * 40}, "longer than"),
        ({"project_key": "P" * 200, "space_key": "DOC"}, "longer than"),
    ],
)
def test_an_unusable_target_is_refused(entry: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        normalize_targets({"projects": [entry]})


def test_a_repository_target_needs_a_slug() -> None:
    with pytest.raises(ValueError, match="repository slug"):
        normalize_targets({"repositories": [{"project_key": "PROJ", "space_key": "DOC"}]})


def test_the_same_level_cannot_be_listed_twice() -> None:
    with pytest.raises(ValueError, match="listed more than once"):
        normalize_targets(
            {
                "projects": [
                    {"project_key": "PROJ", "space_key": "A"},
                    {"project_key": "PROJ", "space_key": "B"},
                ]
            }
        )

    with pytest.raises(ValueError, match="listed more than once"):
        normalize_targets(
            {
                "repositories": [
                    {"project_key": "PROJ", "repository_slug": "a", "space_key": "A"},
                    {"project_key": "PROJ", "repository_slug": "a", "space_key": "B"},
                ]
            }
        )


def test_the_same_slug_under_another_project_is_a_different_repository() -> None:
    config = normalize_targets(
        {
            "repositories": [
                {"project_key": "PROJ", "repository_slug": "api", "space_key": "A"},
                {"project_key": "OTHER", "repository_slug": "api", "space_key": "B"},
            ]
        }
    )

    assert len(config["repositories"]) == 2


def test_both_lists_are_replaced_together() -> None:
    config = normalize_targets({"projects": [{"project_key": "PROJ", "space_key": "DOC"}]})

    assert config["repositories"] == []
    assert config["projects"][0]["space_key"] == "DOC"


def test_a_payload_that_says_neither_list_is_refused() -> None:
    with pytest.raises(ValueError, match="projects or repositories"):
        normalize_targets({})


def test_the_lists_are_bounded() -> None:
    too_many = [
        {"project_key": f"P{index}", "space_key": "DOC"} for index in range(MAX_TARGETS + 1)
    ]

    with pytest.raises(ValueError, match="at most"):
        normalize_targets({"projects": too_many})


# --------------------------------------------------------------------------- #
# What the store hands back
# --------------------------------------------------------------------------- #


def test_an_unreadable_stored_row_reads_as_unset() -> None:
    assert parse_stored_targets("") == empty_targets()
    assert parse_stored_targets("   ") == empty_targets()
    assert parse_stored_targets("{not json") == empty_targets()
    assert parse_stored_targets("[]") == empty_targets()
    assert parse_stored_targets('"a string"') == empty_targets()


def test_one_unusable_stored_entry_does_not_take_the_rest_with_it() -> None:
    stored = json.dumps(
        {
            "projects": [
                {"project_key": "PROJ", "space_key": "PROJSPACE"},
                {"project_key": "BROKEN", "space_key": "TWO WORDS"},
                {"project_key": "GONE"},
            ],
            "repositories": [],
        }
    )

    config = parse_stored_targets(stored)

    assert [entry["project_key"] for entry in config["projects"]] == ["PROJ"]


def test_off_and_unset_survive_a_round_trip() -> None:
    """Absent means "decided elsewhere"; false means "not this repository"."""
    config = normalize_targets(
        {
            "repositories": [
                {"project_key": "PROJ", "repository_slug": "internal-lib", "enabled": False},
                {"project_key": "PROJ", "repository_slug": "my-repo", "space_key": "DOC"},
            ]
        }
    )

    parsed = parse_stored_targets(json.dumps(config))

    assert parsed["repositories"][0]["enabled"] is False
    assert parsed["repositories"][1]["enabled"] is None


def test_a_flag_stored_as_a_string_is_read_as_one() -> None:
    """The settings table stores strings, and a hand-edited row may hold one."""
    config = normalize_targets(
        {
            "repositories": [
                {"project_key": "PROJ", "repository_slug": "my-repo", "enabled": "false"}
            ]
        }
    )

    assert config["repositories"][0]["enabled"] is False


# --------------------------------------------------------------------------- #
# The settings endpoint
# --------------------------------------------------------------------------- #


@pytest.fixture
def targets_client(async_client: AsyncClient, db_session: AsyncSession):
    """A client whose permission gate is open, over the real settings store."""

    class OpenRBACService(RBACService):
        async def require_permission(self, *args, **kwargs) -> None:
            return None

    async def _service() -> RBACService:
        return OpenRBACService(db_session)

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    async def _db_session():
        yield db_session

    app.dependency_overrides[get_rbac_service] = _service
    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = _db_session
    yield async_client
    app.dependency_overrides.pop(get_rbac_service, None)
    app.dependency_overrides.pop(get_current_user_with_token, None)
    app.dependency_overrides.pop(get_db_session, None)


async def _store(db_session: AsyncSession, value: dict) -> None:
    """Put a target configuration in the store the way the application would."""
    service = RBACService(db_session)
    # A setting comes into existence by being read; update only touches existing rows.
    await service.get_setting(SETTING_KEY, default_value="")
    await service.update_setting(setting_key=SETTING_KEY, setting_value=json.dumps(value))


async def _register(db_session: AsyncSession, project_key: str, repository_slug: str) -> None:
    await ProjectRegistryService().register_project(
        "my-app", project_key, repository_slug, db=db_session
    )


async def test_the_settings_show_what_a_repository_resolves_to(
    targets_client: AsyncClient, db_session: AsyncSession, instance_defaults_set
) -> None:
    await _register(db_session, "PROJ", "my-repo")
    await _store(db_session, {"projects": [{"project_key": "PROJ", "space_key": "PROJSPACE"}]})

    response = await targets_client.get(TARGETS_URL)

    assert response.status_code == 200
    body = response.json()
    # The instance defaults are reported so the fallback is visible on the page.
    assert body["instance"]["space_key"] == "DOC"
    assert body["instance"]["parent_page_id"] == "100"
    assert body["instance"]["enabled"] is True
    assert body["instance"]["auto_sync"] is True
    assert body["projects"] == [
        {
            "project_key": "PROJ",
            "space_key": "PROJSPACE",
            "parent_page_id": "",
            "enabled": None,
            "auto_sync": None,
        }
    ]
    assert len(body["resolved"]) == 1
    row = body["resolved"][0]
    assert (row["project_key"], row["repository_slug"]) == ("PROJ", "my-repo")
    assert row["app_name"] == "my-app"
    assert (row["space_key"], row["space_source"]) == ("PROJSPACE", "project")
    assert (row["parent_page_id"], row["parent_source"]) == ("100", "instance")
    assert row["configured"] is True


async def test_a_repository_with_no_target_reports_the_instance_it_falls_back_to(
    targets_client: AsyncClient, db_session: AsyncSession, instance_defaults_set
) -> None:
    await _register(db_session, "PROJ", "my-repo")

    body = (await targets_client.get(TARGETS_URL)).json()

    row = body["resolved"][0]
    assert row["configured"] is False
    assert (row["space_key"], row["space_source"]) == ("DOC", "instance")


async def test_a_target_for_an_unregistered_repository_is_still_reported(
    targets_client: AsyncClient, db_session: AsyncSession, instance_defaults_set
) -> None:
    """Configured but not registered would otherwise look like it did nothing."""
    await _store(
        db_session,
        {
            "repositories": [
                {"project_key": "PROJ", "repository_slug": "not-registered", "space_key": "DOC"}
            ]
        },
    )

    body = (await targets_client.get(TARGETS_URL)).json()

    assert len(body["resolved"]) == 1
    assert body["resolved"][0]["repository_slug"] == "not-registered"
    assert body["resolved"][0]["app_name"] is None


async def test_saving_stores_both_lists_and_answers_with_the_resolution(
    targets_client: AsyncClient, db_session: AsyncSession, instance_defaults_set
) -> None:
    await _register(db_session, "PROJ", "my-repo")

    response = await targets_client.put(
        TARGETS_URL,
        json={
            "projects": [{"project_key": "PROJ", "space_key": "PROJSPACE"}],
            "repositories": [
                {"project_key": "PROJ", "repository_slug": "my-repo", "parent_page_id": "777"}
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["repositories"][0]["parent_page_id"] == "777"
    row = body["resolved"][0]
    assert (row["space_key"], row["parent_page_id"]) == ("PROJSPACE", "777")
    assert row["space_source"] == "project"
    assert row["parent_source"] == "repository"

    # What was written is what is read back, and it is what a sync would use.
    reloaded = (await targets_client.get(TARGETS_URL)).json()
    assert reloaded["repositories"] == body["repositories"]
    assert reloaded["resolved"] == body["resolved"]


async def test_saving_remembers_which_repositories_stay_out_of_the_automatic_sync(
    targets_client: AsyncClient, db_session: AsyncSession, instance_defaults_set
) -> None:
    await _register(db_session, "PROJ", "my-repo")

    response = await targets_client.put(
        TARGETS_URL,
        json={
            "projects": [{"project_key": "PROJ", "space_key": "PROJSPACE"}],
            "repositories": [
                {"project_key": "PROJ", "repository_slug": "my-repo", "auto_sync": False}
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    # Switching the automatic path off is a decision of the repository, and only of
    # the repository: publishing is left to the project's space as before.
    assert body["repositories"][0]["auto_sync"] is False
    assert body["repositories"][0]["enabled"] is None
    row = body["resolved"][0]
    assert (row["auto_sync"], row["auto_sync_source"]) == (False, "repository")
    assert (row["enabled"], row["enabled_source"]) == (True, "instance")

    # Read back as it was written, with the levels that said nothing still empty.
    reloaded = (await targets_client.get(TARGETS_URL)).json()
    assert reloaded["repositories"] == body["repositories"]
    assert reloaded["projects"][0]["auto_sync"] is None


async def test_a_target_that_is_not_usable_is_refused_with_its_reason(
    targets_client: AsyncClient,
) -> None:
    response = await targets_client.put(
        TARGETS_URL,
        json={"projects": [{"project_key": "PROJ", "parent_page_id": "abc"}]},
    )

    assert response.status_code == 400
    assert "is a number" in response.json()["detail"]


async def test_saving_needs_manage_permission(
    targets_client: AsyncClient, db_session: AsyncSession
) -> None:
    # The real gate, with a user who holds no role: the fixture above never refuses.
    app.dependency_overrides[get_rbac_service] = lambda: RBACService(db_session)

    response = await targets_client.put(TARGETS_URL, json={"projects": []})

    assert response.status_code == 403
