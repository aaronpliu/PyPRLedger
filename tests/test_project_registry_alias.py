"""The dependency-database name of a registration.

The dependency database keys applications by a vocabulary of its own, which does
not always follow from the name an administrator registers a repository under: a
repository registered as ``trmyapp`` may have to be asked for as ``myapptr``. The
alias is what closes that gap, and an empty one keeps following the application
name.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.api.v1.endpoints.project_registry import get_rbac_service
from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.main import app
from src.models.auth_user import AuthUser
from src.services.project_registry_service import ProjectRegistryService, dependency_app_name


class AllowingRbac:
    """An administrator, without a role table between the request and the service."""

    async def check_permission(self, **_: Any) -> bool:
        return True


# --------------------------------------------------------------------------- #
# The name the database is asked for
# --------------------------------------------------------------------------- #


def test_an_empty_alias_asks_for_the_application_name() -> None:
    """The documented fallback: what the database keys by, from the registered name."""
    assert dependency_app_name("TrMyApp") == "trmyapp"
    assert dependency_app_name("trmyapp", "") == "trmyapp"
    assert dependency_app_name("TrMyApp", "   ") == "trmyapp"


def test_an_alias_is_asked_for_as_it_was_entered() -> None:
    """An explicitly recorded name is not folded into a shape the database may not use."""
    assert dependency_app_name("trmyapp", "myapptr") == "myapptr"
    assert dependency_app_name("trmyapp", "  myapptr  ") == "myapptr"
    assert dependency_app_name("trmyapp", "MyAppTR") == "MyAppTR"


async def test_a_registration_reaches_the_database_under_its_alias(db_session) -> None:
    service = ProjectRegistryService()
    await service.register_project(
        "trmyapp", "CORE", "app", db=db_session, app_alias="myapptr"
    )

    assert await service.get_dependency_app_name("CORE", "app", db_session) == "myapptr"


async def test_a_registration_without_an_alias_asks_for_the_application_name(db_session) -> None:
    service = ProjectRegistryService()
    await service.register_project("TrMyApp", "CORE", "app", db=db_session)

    assert await service.get_dependency_app_name("CORE", "app", db_session) == "trmyapp"


async def test_clearing_the_alias_puts_the_application_name_back(db_session) -> None:
    service = ProjectRegistryService()
    await service.register_project(
        "trmyapp", "CORE", "app", db=db_session, app_alias="myapptr"
    )

    await service.update_app_alias("CORE", "app", None, db_session)

    assert await service.get_dependency_app_name("CORE", "app", db_session) == "trmyapp"

    # and an empty value clears it the same way the dialog does
    await service.update_app_alias("CORE", "app", "myapptr", db_session)
    await service.update_app_alias("CORE", "app", "   ", db_session)

    assert await service.get_dependency_app_name("CORE", "app", db_session) == "trmyapp"


async def test_an_unregistered_repository_still_resolves_to_the_default(db_session) -> None:
    """The alias belongs to a registration: without one, nothing about this changed."""
    service = ProjectRegistryService()

    assert await service.get_dependency_app_name("CORE", "unregistered", db_session) == "unknown"


async def test_the_alias_of_an_unregistered_repository_is_refused(db_session) -> None:
    service = ProjectRegistryService()

    with pytest.raises(ValueError):
        await service.update_app_alias("CORE", "unregistered", "myapptr", db_session)


async def test_registering_an_alias_for_a_known_pair_updates_it(db_session) -> None:
    """A registration that already exists gains the alias instead of a second entry."""
    service = ProjectRegistryService()
    await service.register_project("trmyapp", "CORE", "app", db=db_session)

    await service.register_project(
        "trmyapp", "CORE", "app", db=db_session, app_alias="myapptr"
    )

    assert await service.get_dependency_app_name("CORE", "app", db_session) == "myapptr"
    assert len(await service.list_all_projects(db_session)) == 1


# --------------------------------------------------------------------------- #
# The admin endpoint that sets it
# --------------------------------------------------------------------------- #


async def test_endpoint_sets_and_clears_the_alias(async_client, db_session) -> None:
    await ProjectRegistryService().register_project("trmyapp", "CORE", "app", db=db_session)

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    async def _db_session() -> Any:
        yield db_session

    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = _db_session
    app.dependency_overrides[get_rbac_service] = lambda: AllowingRbac()
    try:
        response = await async_client.put(
            "/api/v1/admin/registry/app-alias",
            params={
                "project_key": "CORE",
                "repository_slug": "app",
                "app_alias": "myapptr",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["app_alias"] == "myapptr"
        # the answer names what the database will be asked for, not just what was stored
        assert response.json()["dependency_app_name"] == "myapptr"

        cleared = await async_client.put(
            "/api/v1/admin/registry/app-alias",
            params={"project_key": "CORE", "repository_slug": "app", "app_alias": ""},
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["app_alias"] is None
        assert cleared.json()["dependency_app_name"] == "trmyapp"

        missing = await async_client.put(
            "/api/v1/admin/registry/app-alias",
            params={
                "project_key": "CORE",
                "repository_slug": "unregistered",
                "app_alias": "myapptr",
            },
        )
        assert missing.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_with_token, None)
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_rbac_service, None)


async def test_endpoint_lists_the_alias_with_every_registration(async_client, db_session) -> None:
    """The registry page reads the alias off the listing it already asks for."""
    await ProjectRegistryService().register_project(
        "trmyapp", "CORE", "app", db=db_session, app_alias="myapptr"
    )

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    async def _db_session() -> Any:
        yield db_session

    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = _db_session
    app.dependency_overrides[get_rbac_service] = lambda: AllowingRbac()
    try:
        response = await async_client.get("/api/v1/admin/registry/projects")

        assert response.status_code == 200, response.text
        items = response.json()["items"]
        assert [(item["app_name"], item["app_alias"]) for item in items] == [
            ("trmyapp", "myapptr")
        ]
    finally:
        app.dependency_overrides.pop(get_current_user_with_token, None)
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_rbac_service, None)
