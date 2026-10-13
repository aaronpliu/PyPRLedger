"""What a registration records about where its repository lives.

The registry is what the release pages resolve a repository's provider from, and its
provider column cannot be left empty - so a registration that had to guess would have
every read of that repository addressed to the wrong instance, with nothing on the
page able to tell. A provider that was named is a decision and is kept as it stands;
a registration that names none takes the one its project is on.
"""

from __future__ import annotations

from typing import Any

from src.core.git_provider import GitProvider
from src.models.project import Project
from src.models.project_registry import ProjectRegistry
from src.services.project_registry_service import ProjectRegistryService


async def seed_project(db_session: Any, provider: str) -> None:
    """Store the project the repositories of these tests belong to."""
    db_session.add(
        Project(
            project_id=1,
            project_name="AI",
            project_key="AI",
            project_url="https://bitbucket.org/aaronpliu",
            git_provider=provider,
        )
    )
    await db_session.flush()


# --------------------------------------------------------------------------- #
# A repository that registers itself
# --------------------------------------------------------------------------- #


async def test_an_auto_registration_takes_the_provider_of_its_project(db_session: Any) -> None:
    """The column cannot be left empty, so the project is what it is read from."""
    await seed_project(db_session, GitProvider.BITBUCKET_CLOUD.value)

    entry = await ProjectRegistryService().auto_register_project(
        "AI", "pylang", "mylang", db_session
    )

    assert entry.git_provider == GitProvider.BITBUCKET_CLOUD.value


async def test_an_auto_registration_of_an_unstored_project_takes_the_default(
    db_session: Any,
) -> None:
    """Nothing stored the project, so the configured default stands for it."""
    entry = await ProjectRegistryService().auto_register_project(
        "GHOST", "pylang", "mylang", db_session
    )

    assert entry.git_provider == ProjectRegistry.DEFAULT_PROVIDER


# --------------------------------------------------------------------------- #
# A registration somebody makes
# --------------------------------------------------------------------------- #


async def test_a_registration_naming_no_provider_takes_the_projects(db_session: Any) -> None:
    """The manual path resolves the same way the automatic one does."""
    await seed_project(db_session, GitProvider.GITHUB_ENTERPRISE.value)

    entry = await ProjectRegistryService().register_project(
        "pylang", "AI", "pylang", db=db_session
    )

    assert entry.git_provider == GitProvider.GITHUB_ENTERPRISE.value


async def test_a_registration_naming_a_provider_is_registered_under_it(db_session: Any) -> None:
    """Naming one is a decision, and the default is a value like any other."""
    await seed_project(db_session, GitProvider.BITBUCKET_CLOUD.value)

    entry = await ProjectRegistryService().register_project(
        "pylang", "AI", "pylang", db=db_session, git_provider=GitProvider.BITBUCKET_SERVER.value
    )

    assert entry.git_provider == GitProvider.BITBUCKET_SERVER.value


async def test_naming_a_provider_settles_a_registration_that_guessed_wrong(
    db_session: Any,
) -> None:
    """A registration made before the project knew better can be put right."""
    await seed_project(db_session, GitProvider.BITBUCKET_CLOUD.value)
    service = ProjectRegistryService()
    entry = await service.register_project("pylang", "AI", "pylang", db=db_session)
    assert entry.git_provider == GitProvider.BITBUCKET_CLOUD.value

    corrected = await service.register_project(
        "pylang", "AI", "pylang", db=db_session, git_provider=GitProvider.BITBUCKET_SERVER.value
    )

    assert corrected.git_provider == GitProvider.BITBUCKET_SERVER.value


async def test_moving_a_registration_between_applications_leaves_its_provider_alone(
    db_session: Any,
) -> None:
    """A move names a new application, not a provider: what is stored stands."""
    await seed_project(db_session, GitProvider.BITBUCKET_CLOUD.value)
    service = ProjectRegistryService()
    await service.register_project(
        "pylang", "AI", "pylang", db=db_session, git_provider=GitProvider.GITHUB_ENTERPRISE.value
    )

    moved = await service.update_project_app("AI", "pylang", "another-app", db_session)

    assert moved.app_name == "another-app"
    assert moved.git_provider == GitProvider.GITHUB_ENTERPRISE.value
