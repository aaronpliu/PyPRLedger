import logging
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.project_registry import ProjectRegistry


logger = logging.getLogger(__name__)


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

    async def register_project(
        self,
        app_name: str,
        project_key: str,
        repository_slug: str,
        description: str | None = None,
        db: AsyncSession = None,
    ) -> ProjectRegistry:
        """
        Register a new project-repo pair to an app

        Args:
            app_name: Application name
            project_key: Project key
            repository_slug: Repository slug
            description: Optional description
            db: Database session

        Returns:
            Created ProjectRegistry entry

        Raises:
            ValueError: If project-repo pair already registered to different app
        """
        # Check if already registered
        existing = await self._get_registry_entry(project_key, repository_slug, db)

        if existing:
            if existing.app_name != app_name:
                raise ValueError(
                    f"Project {project_key}/{repository_slug} already registered to '{existing.app_name}'. "
                    f"Cannot reassign to '{app_name}'."
                )
            # Already registered to same app, update description if provided
            if description:
                existing.description = description
                await db.commit()
                await db.refresh(existing)
            return existing

        # Create new registration
        registry = ProjectRegistry(
            app_name=app_name,
            project_key=project_key,
            repository_slug=repository_slug,
            description=description or f"Registered to {app_name}",
        )

        db.add(registry)
        await db.commit()
        await db.refresh(registry)

        logger.info(f"Registered {project_key}/{repository_slug} to app '{app_name}'")
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
