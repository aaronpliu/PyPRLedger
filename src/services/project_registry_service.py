import logging
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.git_provider import GitProvider
from src.models.project_registry import ProjectRegistry


logger = logging.getLogger(__name__)


def dependency_app_name(app_name: str, app_alias: str | None = None) -> str:
    """The application name the dependency database is asked for.

    The registry holds the name an administrator registered the repository under,
    while the dependency database keys its applications by a vocabulary of its own
    - a lower-case enum that does not always follow from that name: a repository
    registered as ``trmyapp`` may have to be asked for as ``myapptr``. That
    difference is recorded as the repository's alias, and an alias is what is asked
    for, **exactly as it was entered**: a name an administrator set explicitly is
    sent as it stands rather than folded into a shape the database may not use.

    Without an alias the application name is asked for in the form the database
    keys by, so a registration that needs no alias still finds its record.
    """
    alias = (app_alias or "").strip()
    if alias:
        return alias
    return app_name.strip().lower()


class ProjectRegistryService:
    """Service for managing project-to-application registry"""

    DEFAULT_APP_NAME = "Unknown"

    def __init__(self):
        """Initialize the project registry service"""
        pass

    async def get_app_name(self, project_key: str, repository_slug: str, db: AsyncSession) -> str:
        """
        Resolve app_name from project_key and repository_slug

        Args:
            project_key: The project key
            repository_slug: The repository slug
            db: Database session

        Returns:
            app_name string, defaults to 'Unknown' if not registered
        """
        try:
            # Query registry for this project-repo pair
            query = select(ProjectRegistry).where(
                and_(
                    ProjectRegistry.project_key == project_key,
                    ProjectRegistry.repository_slug == repository_slug,
                )
            )
            result = await db.execute(query)
            registry_entry = result.scalar_one_or_none()

            if registry_entry:
                return registry_entry.app_name

            # Auto-register to default app if not found
            logger.info(
                f"Project {project_key}/{repository_slug} not registered, "
                f"auto-registering to '{self.DEFAULT_APP_NAME}'"
            )
            await self.auto_register_project(
                project_key, repository_slug, self.DEFAULT_APP_NAME, db
            )
            return self.DEFAULT_APP_NAME

        except Exception as e:
            logger.error(
                f"Failed to resolve app_name for {project_key}/{repository_slug}: {str(e)}"
            )
            return self.DEFAULT_APP_NAME

    async def get_dependency_app_name(
        self, project_key: str, repository_slug: str, db: AsyncSession
    ) -> str:
        """What the dependency database is asked for, for one repository.

        The alias belongs to the registration it overrides, so the two are read
        together: a repository that is not registered is auto-registered under the
        default name, exactly as :meth:`get_app_name` does, and no alias can exist
        for it yet.

        Args:
            project_key: The project key
            repository_slug: The repository slug
            db: Database session

        Returns:
            The name to ask the dependency database for
        """
        try:
            entry = await self._get_registry_entry(project_key, repository_slug, db)
            if entry is None:
                app_name = await self.get_app_name(project_key, repository_slug, db)
                return dependency_app_name(app_name)
            return dependency_app_name(entry.app_name, entry.app_alias)

        except Exception as e:
            logger.error(
                f"Failed to resolve the dependency app name for "
                f"{project_key}/{repository_slug}: {str(e)}"
            )
            return dependency_app_name(self.DEFAULT_APP_NAME)

    async def update_app_alias(
        self,
        project_key: str,
        repository_slug: str,
        app_alias: str | None,
        db: AsyncSession,
    ) -> ProjectRegistry:
        """Set or clear the dependency-database name of one repository.

        An empty value clears it, and from then on the application name is asked
        for: that is what the alias following the application name means.

        Args:
            project_key: The project key
            repository_slug: The repository slug
            app_alias: The name the dependency database knows, or None to clear it
            db: Database session

        Returns:
            The updated registry entry

        Raises:
            ValueError: If the repository is not registered
        """
        existing = await self._get_registry_entry(project_key, repository_slug, db)

        if not existing:
            raise ValueError(f"Project {project_key}/{repository_slug} is not registered")

        existing.app_alias = (app_alias or "").strip() or None
        await db.commit()
        await db.refresh(existing)

        logger.info(
            f"Set the dependency app alias of {project_key}/{repository_slug} to "
            f"'{existing.app_alias or existing.app_name}'"
        )
        return existing

    async def get_git_provider(
        self, project_key: str, repository_slug: str, db: AsyncSession
    ) -> str | None:
        """
        Resolve the git provider a repository is registered under

        Args:
            project_key: The project key
            repository_slug: The repository slug
            db: Database session

        Returns:
            The provider name, or None when the pair is not registered
        """
        registry_entry = await self._get_registry_entry(project_key, repository_slug, db)
        return registry_entry.git_provider if registry_entry else None

    async def get_app_names_batch(
        self, project_repo_pairs: list[tuple[str, str]], db: AsyncSession
    ) -> dict[tuple[str, str], str]:
        """
        Resolve app_names for multiple project-repo pairs in a single query

        Args:
            project_repo_pairs: List of (project_key, repository_slug) tuples
            db: Database session

        Returns:
            Dictionary mapping (project_key, repository_slug) to app_name
        """
        if not project_repo_pairs:
            return {}

        # Build conditions for batch query
        conditions = [
            and_(
                ProjectRegistry.project_key == pk,
                ProjectRegistry.repository_slug == rs,
            )
            for pk, rs in project_repo_pairs
        ]

        query = select(ProjectRegistry).where(or_(*conditions))
        result = await db.execute(query)
        registries = result.scalars().all()

        # Build mapping
        mapping = {}
        for registry in registries:
            key = (registry.project_key, registry.repository_slug)
            mapping[key] = registry.app_name

        # Auto-register missing pairs
        for pk, rs in project_repo_pairs:
            if (pk, rs) not in mapping:
                mapping[(pk, rs)] = self.DEFAULT_APP_NAME
                # Schedule auto-registration
                await self.auto_register_project(pk, rs, self.DEFAULT_APP_NAME, db)

        return mapping

    async def list_projects_by_app(
        self, app_name: str | None = None, db: AsyncSession = None
    ) -> list[ProjectRegistry]:
        """
        Get all (project_key, repository_slug) pairs for an app

        Args:
            app_name: Filter by specific app_name (optional)
            db: Database session

        Returns:
            List of ProjectRegistry entries
        """
        query = select(ProjectRegistry)
        if app_name:
            query = query.where(ProjectRegistry.app_name == app_name)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def list_all_projects(self, db: AsyncSession) -> list[ProjectRegistry]:
        """
        Get all registered projects across all applications

        Args:
            db: Database session

        Returns:
            List of all ProjectRegistry entries
        """
        query = select(ProjectRegistry).order_by(
            ProjectRegistry.app_name,
            ProjectRegistry.project_key,
            ProjectRegistry.repository_slug,
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def list_projects_paginated(
        self,
        db: AsyncSession,
        app_name: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ProjectRegistry], int]:
        """
        Get paginated list of registered projects with optional filters

        Args:
            db: Database session
            app_name: Filter by application name (optional)
            search: Search term for project_key, repository_slug, or description (optional)
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (list of ProjectRegistry entries, total count)
        """
        query = select(ProjectRegistry)

        if app_name:
            query = query.where(ProjectRegistry.app_name == app_name)

        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    ProjectRegistry.project_key.ilike(search_pattern),
                    ProjectRegistry.repository_slug.ilike(search_pattern),
                    ProjectRegistry.description.ilike(search_pattern),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(
            ProjectRegistry.app_name,
            ProjectRegistry.project_key,
            ProjectRegistry.repository_slug,
        )

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def register_project(
        self,
        app_name: str,
        project_key: str,
        repository_slug: str,
        description: str | None = None,
        db: AsyncSession = None,
        git_provider: str = ProjectRegistry.DEFAULT_PROVIDER,
        app_alias: str | None = None,
    ) -> ProjectRegistry:
        """
        Register a new project-repo pair to an app

        Args:
            app_name: Application name
            project_key: Project key
            repository_slug: Repository slug
            description: Optional description
            db: Database session
            git_provider: Git provider (bitbucket_server, github_enterprise)
            app_alias: Optional name the dependency database knows the app as

        Returns:
            Created ProjectRegistry entry

        Raises:
            ValueError: If project-repo pair already registered to different app or invalid git_provider
        """
        # Validate git_provider
        if not GitProvider.is_valid(git_provider):
            raise ValueError(
                f"Invalid git_provider '{git_provider}'. "
                f"Must be one of: {', '.join(sorted(GitProvider.values()))}"
            )

        # Check if already registered
        existing = await self._get_registry_entry(project_key, repository_slug, db)

        if existing:
            if existing.app_name != app_name:
                raise ValueError(
                    f"Project {project_key}/{repository_slug} already registered to '{existing.app_name}'. "
                    f"Cannot reassign to '{app_name}'."
                )
            # Already registered to same app, update description, provider and/or
            # dependency database name if provided
            updated = False
            if description:
                existing.description = description
                updated = True
            if (
                git_provider != ProjectRegistry.DEFAULT_PROVIDER
                and existing.git_provider != git_provider
            ):
                existing.git_provider = git_provider
                updated = True
            alias = (app_alias or "").strip() or None
            if alias is not None and existing.app_alias != alias:
                existing.app_alias = alias
                updated = True
            if updated:
                await db.commit()
                await db.refresh(existing)
            return existing

        # Create new registration
        registry = ProjectRegistry(
            app_name=app_name,
            project_key=project_key,
            repository_slug=repository_slug,
            git_provider=git_provider,
            app_alias=(app_alias or "").strip() or None,
            description=description or f"Registered to {app_name}",
        )

        db.add(registry)
        await db.commit()
        await db.refresh(registry)

        logger.info(
            f"Registered {project_key}/{repository_slug} to app '{app_name}' (provider: {git_provider})"
        )
        return registry

    async def unregister_project(
        self, project_key: str, repository_slug: str, db: AsyncSession
    ) -> bool:
        """
        Remove a project-repo pair from registry

        Args:
            project_key: Project key
            repository_slug: Repository slug
            db: Database session

        Returns:
            True if unregistered, False if not found
        """
        existing = await self._get_registry_entry(project_key, repository_slug, db)

        if not existing:
            return False

        await db.delete(existing)
        await db.commit()

        logger.info(f"Unregistered {project_key}/{repository_slug} from app '{existing.app_name}'")
        return True

    async def update_project_app(
        self,
        project_key: str,
        repository_slug: str,
        new_app_name: str,
        db: AsyncSession,
    ) -> ProjectRegistry:
        """
        Move a project-repo pair to a different app

        Args:
            project_key: Project key
            repository_slug: Repository slug
            new_app_name: New application name
            db: Database session

        Returns:
            Updated ProjectRegistry entry
        """
        existing = await self._get_registry_entry(project_key, repository_slug, db)

        if not existing:
            # Register as new
            return await self.register_project(new_app_name, project_key, repository_slug, db)

        # Update existing
        existing.app_name = new_app_name
        await db.commit()
        await db.refresh(existing)

        logger.info(
            f"Moved {project_key}/{repository_slug} from '{existing.app_name}' to '{new_app_name}'"
        )
        return existing

    async def list_all_apps(self, db: AsyncSession) -> list[dict[str, Any]]:
        """
        List all registered applications with their project counts

        Args:
            db: Database session

        Returns:
            List of dicts with app_name and project_count
        """
        query = (
            select(
                ProjectRegistry.app_name,
                func.count(ProjectRegistry.id).label("project_count"),
            )
            .group_by(ProjectRegistry.app_name)
            .order_by(ProjectRegistry.app_name)
        )

        result = await db.execute(query)
        return [
            {"app_name": row.app_name, "project_count": row.project_count}
            for row in result.fetchall()
        ]

    async def _get_registry_entry(
        self, project_key: str, repository_slug: str, db: AsyncSession
    ) -> ProjectRegistry | None:
        """Helper to get a single registry entry"""
        query = select(ProjectRegistry).where(
            and_(
                ProjectRegistry.project_key == project_key,
                ProjectRegistry.repository_slug == repository_slug,
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def auto_register_project(
        self, project_key: str, repository_slug: str, app_name: str, db: AsyncSession
    ) -> ProjectRegistry:
        """
        Auto-register a project-repo pair (internal use)

        Args:
            project_key: Project key
            repository_slug: Repository slug
            app_name: Application name (default: 'Unknown')
            db: Database session

        Returns:
            Created ProjectRegistry entry
        """
        try:
            registry = ProjectRegistry(
                app_name=app_name,
                project_key=project_key,
                repository_slug=repository_slug,
                description=f"Auto-registered to {app_name}",
            )
            db.add(registry)
            await db.commit()
            await db.refresh(registry)
            logger.info(f"Auto-registered {project_key}/{repository_slug} to '{app_name}'")
            return registry
        except Exception as e:
            logger.error(f"Failed to auto-register {project_key}/{repository_slug}: {str(e)}")
            # Return a temporary object even if save failed
            return ProjectRegistry(
                app_name=app_name,
                project_key=project_key,
                repository_slug=repository_slug,
                description="Auto-registered (pending)",
            )
