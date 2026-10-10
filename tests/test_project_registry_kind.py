"""What a registration is: an application, or a package.

The registry serves two purposes - resolving a repository to the application the
dependency database knows it by, and resolving a package name back to the repository
it lives in. Only the first is something the pages that read an application's
releases can use: the dependency database holds release records for applications
alone, and a package repository offered beside them is a dead end.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.endpoints.project_registry import get_rbac_service
from src.core.database import get_db_session
from src.core.git_provider import GitProvider
from src.core.permissions import get_current_user_with_token
from src.main import app
from src.models.auth_user import AuthUser
from src.models.project import Project
from src.models.project_registry import ProjectRegistry
from src.models.repository import Repository
from src.services.project_registry_service import ProjectRegistryService


class AllowingRbac:
    """An administrator, without a role table between the request and the service."""

    async def check_permission(self, **_: Any) -> bool:
        return True


# --------------------------------------------------------------------------- #
# What a registration says it is
# --------------------------------------------------------------------------- #


async def test_a_registration_is_an_application_unless_it_says_otherwise(
    db_session: AsyncSession,
) -> None:
    """This table began as an application map, so saying nothing keeps saying that."""
    entry = await ProjectRegistryService().register_project("core-app", "CORE", "app", db=db_session)

    assert entry.registry_kind == ProjectRegistry.KIND_APPLICATION


async def test_a_registration_can_be_made_a_package(db_session: AsyncSession) -> None:
    """A library is registered here so a dependency can be compared in it, not to be read."""
    entry = await ProjectRegistryService().register_project(
        "core-pkg-a",
        "CORE",
        "pkg-a",
        db=db_session,
        app_alias="packageA",
        registry_kind=ProjectRegistry.KIND_PACKAGE,
    )

    assert entry.registry_kind == ProjectRegistry.KIND_PACKAGE


async def test_a_kind_no_registration_has_is_refused(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError):
        await ProjectRegistryService().register_project(
            "core-app", "CORE", "app", db=db_session, registry_kind="library"
        )


async def test_marking_a_registration_moves_it_between_the_lists(
    db_session: AsyncSession,
) -> None:
    service = ProjectRegistryService()
    await service.register_project(
        "core-pkg-a", "CORE", "pkg-a", db=db_session, registry_kind=ProjectRegistry.KIND_PACKAGE
    )

    entry = await service.update_registry_kind(
        "CORE", "pkg-a", ProjectRegistry.KIND_APPLICATION, db_session
    )

    assert entry.registry_kind == ProjectRegistry.KIND_APPLICATION


async def test_marking_an_unregistered_repository_is_refused(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError):
        await ProjectRegistryService().update_registry_kind(
            "CORE", "unregistered", ProjectRegistry.KIND_PACKAGE, db_session
        )


async def test_re_registering_a_known_pair_can_change_what_it_is(db_session: AsyncSession) -> None:
    """The register dialog can correct a registration made as the wrong kind."""
    service = ProjectRegistryService()
    await service.register_project("core-pkg-a", "CORE", "pkg-a", db=db_session)

    await service.register_project(
        "core-pkg-a", "CORE", "pkg-a", db=db_session, registry_kind=ProjectRegistry.KIND_PACKAGE
    )

    assert len(await service.list_all_projects(db_session)) == 1
    entry, _ = await service.find_dependency_repository("core-pkg-a", "CORE", db_session)
    assert entry is not None
    assert entry.registry_kind == ProjectRegistry.KIND_PACKAGE

    # and registering again without a kind leaves it where it is, so a dialog that
    # says nothing cannot quietly demote a package back into the application list
    await service.register_project("core-pkg-a", "CORE", "pkg-a", db=db_session)

    entry, _ = await service.find_dependency_repository("core-pkg-a", "CORE", db_session)
    assert entry is not None
    assert entry.registry_kind == ProjectRegistry.KIND_PACKAGE


# --------------------------------------------------------------------------- #
# The repository listing the pickers read
# --------------------------------------------------------------------------- #


async def seed_project(db: AsyncSession) -> None:
    """One project holding an application, a package, and a repository no one registered.

    The three cases a listing has to tell apart: a registration marked as an
    application, one marked as a package, and a repository with no registration at
    all - which is what a page that does not ask for a kind still wants to see.
    """
    db.add(
        Project(
            project_id=1,
            project_key="CORE",
            project_name="Core",
            project_url="http://localhost:7990/projects/CORE",
            git_provider=GitProvider.BITBUCKET_SERVER.value,
        )
    )
    db.add_all(
        [
            Repository(
                repository_id=1,
                project_id=1,
                repository_name="Application",
                repository_slug="app",
                repository_url="http://localhost:7990/projects/CORE/repos/app",
            ),
            Repository(
                repository_id=2,
                project_id=1,
                repository_name="Package A",
                repository_slug="pkg-a",
                repository_url="http://localhost:7990/projects/CORE/repos/pkg-a",
            ),
            Repository(
                repository_id=3,
                project_id=1,
                repository_name="Unregistered",
                repository_slug="unknown",
                repository_url="http://localhost:7990/projects/CORE/repos/unknown",
            ),
        ]
    )
    await db.commit()

    service = ProjectRegistryService()
    await service.register_project("core-app", "CORE", "app", db=db)
    await service.register_project(
        "core-pkg-a",
        "CORE",
        "pkg-a",
        db=db,
        app_alias="packageA",
        registry_kind=ProjectRegistry.KIND_PACKAGE,
    )


def override_db(db: AsyncSession):
    """Hand the endpoint the test's session."""

    async def _db_session() -> Any:
        yield db

    return _db_session


async def test_the_listing_offers_applications_alone(async_client, db_session) -> None:
    """The pages that read an application's releases ask for a kind, and get it."""
    await seed_project(db_session)

    app.dependency_overrides[get_db_session] = override_db(db_session)
    try:
        applications = await async_client.get(
            "/api/v1/projects/key/CORE/repositories", params={"registry_kind": "application"}
        )

        assert applications.status_code == 200, applications.text
        assert [item["repository_slug"] for item in applications.json()] == ["app"]
        assert applications.json()[0]["registry_kind"] == ProjectRegistry.KIND_APPLICATION

        packages = await async_client.get(
            "/api/v1/projects/key/CORE/repositories", params={"registry_kind": "package"}
        )

        assert packages.status_code == 200, packages.text
        assert [item["repository_slug"] for item in packages.json()] == ["pkg-a"]

        # a page that asks for no kind keeps seeing every repository, each carrying
        # what the registry says it is - null where nothing is registered at all
        everything = await async_client.get("/api/v1/projects/key/CORE/repositories")

        assert everything.status_code == 200, everything.text
        assert [(item["repository_slug"], item["registry_kind"]) for item in everything.json()] == [
            ("app", ProjectRegistry.KIND_APPLICATION),
            ("pkg-a", ProjectRegistry.KIND_PACKAGE),
            ("unknown", None),
        ]
    finally:
        app.dependency_overrides.pop(get_db_session, None)


async def test_the_listing_refuses_a_kind_no_registration_has(async_client, db_session) -> None:
    """A filter that can never match is a mistake, not an empty page."""
    app.dependency_overrides[get_db_session] = override_db(db_session)
    try:
        response = await async_client.get(
            "/api/v1/projects/key/CORE/repositories", params={"registry_kind": "library"}
        )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db_session, None)


# --------------------------------------------------------------------------- #
# The admin endpoint that marks one
# --------------------------------------------------------------------------- #


async def test_endpoint_marks_a_registration(async_client, db_session) -> None:
    await ProjectRegistryService().register_project("core-app", "CORE", "app", db=db_session)

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = override_db(db_session)
    app.dependency_overrides[get_rbac_service] = lambda: AllowingRbac()
    try:
        response = await async_client.put(
            "/api/v1/admin/registry/kind",
            params={
                "project_key": "CORE",
                "repository_slug": "app",
                "registry_kind": "package",
            },
        )

        assert response.status_code == 200, response.text
        assert response.json()["registry_kind"] == ProjectRegistry.KIND_PACKAGE

        # a kind no registration has is refused before anything is written
        invalid = await async_client.put(
            "/api/v1/admin/registry/kind",
            params={
                "project_key": "CORE",
                "repository_slug": "app",
                "registry_kind": "library",
            },
        )

        assert invalid.status_code == 422

        # and a repository that is not registered is not marked
        missing = await async_client.put(
            "/api/v1/admin/registry/kind",
            params={
                "project_key": "CORE",
                "repository_slug": "unregistered",
                "registry_kind": "package",
            },
        )

        assert missing.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_with_token, None)
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_rbac_service, None)


async def test_endpoint_lists_what_each_registration_is(async_client, db_session) -> None:
    """The registry page reads the kind off the listing it already asks for."""
    await ProjectRegistryService().register_project(
        "core-pkg-a", "CORE", "pkg-a", db=db_session, registry_kind=ProjectRegistry.KIND_PACKAGE
    )

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = override_db(db_session)
    app.dependency_overrides[get_rbac_service] = lambda: AllowingRbac()
    try:
        response = await async_client.get("/api/v1/admin/registry/projects")

        assert response.status_code == 200, response.text
        items = response.json()["items"]
        assert [(item["app_name"], item["registry_kind"]) for item in items] == [
            ("core-pkg-a", ProjectRegistry.KIND_PACKAGE)
        ]
    finally:
        app.dependency_overrides.pop(get_current_user_with_token, None)
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_rbac_service, None)
