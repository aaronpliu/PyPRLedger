import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import (
    ProjectNotFoundException,
    ResourceAlreadyExistsException,
)
from src.models.project import Project
from src.models.pull_request import PullRequestReview
from src.models.repository import Repository
from src.schemas.project import (
    ProjectCreate,
    ProjectFilter,
    ProjectResponse,
    ProjectStats,
    ProjectUpdate,
)
from src.utils.metrics import MetricsCollector
from src.utils.redis import get_redis_client


logger = logging.getLogger(__name__)


class ProjectService:
    """Service for managing projects"""

    def __init__(self, metrics_collector: MetricsCollector | None = None):
        """Initialize the project service"""
        self.redis_client = get_redis_client()
        self.metrics = metrics_collector or MetricsCollector()

    def _get_cache_key(self, project_id: int) -> str:
        """Generate cache key for a project"""
        return f"project:{project_id}"

    def _get_project_key_cache_key(self, project_key: str) -> str:
        """Generate cache key for a project key"""
        return f"project:key:{project_key}"

    def _get_list_cache_key(self, filters: dict[str, Any], page: int, page_size: int) -> str:
        """Generate cache key for project list"""
        filter_str = ":".join(f"{k}={v}" for k, v in sorted(filters.items()) if v is not None)
        return f"projects:list:{filter_str}:{page}:{page_size}"

    async def _get_project_from_cache(self, project_id: int) -> dict[str, Any] | None:
        """Try to get project from cache"""
        try:
            cached = await self.redis_client.get(self._get_cache_key(project_id))
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Failed to get project from cache: {str(e)}")
        return None

    async def _set_project_in_cache(self, project_id: int, project_data: dict[str, Any]) -> None:
        """Store project in cache"""
        try:
            await self.redis_client.setex(
                self._get_cache_key(project_id),
                settings.CACHE_TTL_PROJECTS,
                json.dumps(project_data),
            )
        except Exception as e:
            logger.warning(f"Failed to set project in cache: {str(e)}")

    async def _invalidate_project_cache(self, project_id: int, project_key: str) -> None:
        """Invalidate project cache entries"""
        try:
            await self.redis_client.delete(self._get_cache_key(project_id))
            await self.redis_client.delete(self._get_project_key_cache_key(project_key))
        except Exception as e:
            logger.warning(f"Failed to invalidate project cache: {str(e)}")

    async def _invalidate_list_cache(self) -> None:
        """Invalidate all project list cache entries"""
        try:
            keys = await self.redis_client.keys("projects:list:*")
            if keys:
                await self.redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"Failed to invalidate list cache: {str(e)}")

    async def _invalidate_stats_cache(self) -> None:
        """Invalidate project statistics cache"""
        try:
            keys = await self.redis_client.keys("stats:projects*")
            if keys:
                await self.redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"Failed to invalidate stats cache: {str(e)}")

    async def create_project(
        self, project_data: ProjectCreate, db: AsyncSession
    ) -> ProjectResponse:
        """
        Create a new project

        Args:
            project_data: The project data to create
            db: Database session

        Returns:
            ProjectResponse: The created project

        Raises:
            ResourceAlreadyExistsException: If a project with the same ID or key already exists
        """
        # Check if project_id already exists
        existing_id = await db.execute(
            select(Project).where(Project.project_id == project_data.project_id)
        )
        if existing_id.scalar_one_or_none():
            raise ResourceAlreadyExistsException(
                message=f"Project with ID {project_data.project_id} already exists"
            )

        # Check if project_key already exists
        existing_key = await db.execute(
            select(Project).where(Project.project_key == project_data.project_key)
        )
        if existing_key.scalar_one_or_none():
            raise ResourceAlreadyExistsException(
                message=f"Project with key {project_data.project_key} already exists"
            )

        # Create new project
        new_project = Project.from_dict(project_data.model_dump())

        db.add(new_project)
        await db.flush()
        await db.refresh(new_project)

        # Cache the new project
        project_dict = new_project.to_dict()
        await self._set_project_in_cache(new_project.id, project_dict)

        # Invalidate list cache
        await self._invalidate_list_cache()

        # Update metrics
        self.metrics.increment_project_count()

        logger.info(f"Created new project: {new_project.project_id} (ID: {new_project.id})")
        return ProjectResponse(**project_dict)

    async def upsert_project(
        self, project_data: ProjectCreate, db: AsyncSession
    ) -> tuple[Project, bool]:
        """
        Upsert a project - create if not exists, update if exists

        Args:
            project_data: The project data to upsert
            db: Database session

        Returns:
            Tuple[Project, bool]: The project and whether it was created
        """
        # Check if project exists by business ID
        existing = await db.execute(
            select(Project).where(Project.project_id == project_data.project_id)
        )
        project = existing.scalar_one_or_none()

        created = False
        if not project:
            # Create new project
            project = Project.from_dict(project_data.model_dump())
            db.add(project)
            created = True
            logger.info(f"Created new project: {project.project_id}")
        else:
            # Update existing project
            project.update(project_data.model_dump())
            logger.info(f"Updated existing project: {project.project_id}")

        await db.flush()
        await db.refresh(project)

        # Cache the project
        await self._set_project_in_cache(project.id, project.to_dict())

        # Invalidate list cache if created
        if created:
            await self._invalidate_list_cache()
            self.metrics.increment_project_count()

        return project, created

    async def get_project_by_id(
        self, project_id: int, db: AsyncSession, use_cache: bool = True
    ) -> Project | None:
        """
        Get a project by ID

        Args:
            project_id: The project database ID
            db: Database session
            use_cache: Whether to use cache

        Returns:
            Project: The project, or None if not found
        """
        # Try cache first
        if use_cache:
            cached = await self._get_project_from_cache(project_id)
            if cached:
                logger.debug(f"Retrieved project from cache: {project_id}")
                return Project.from_dict(cached)

        # Query database
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()

        if project:
            # Cache the result
            await self._set_project_in_cache(project_id, project.to_dict())

        return project

    async def get_project_by_project_id(
        self, project_id: str, db: AsyncSession, use_cache: bool = True
    ) -> Project | None:
        """
        Get a project by project identifier

        Args:
            project_id: The project identifier
            db: Database session
            use_cache: Whether to use cache

        Returns:
            Project: The project, or None if not found
        """
        # Query database
        result = await db.execute(select(Project).where(Project.project_id == project_id))
        project = result.scalar_one_or_none()

        if project and use_cache:
            # Cache the result
            await self._set_project_in_cache(project.id, project.to_dict())

        return project

    async def get_project_by_key(
        self, project_key: str, db: AsyncSession, use_cache: bool = True
    ) -> Project | None:
        """
        Get a project by project key

        Args:
            project_key: The project key
            db: Database session
            use_cache: Whether to use cache

        Returns:
            Project: The project, or None if not found
        """
        # Try cache first
        if use_cache:
            try:
                cache_key = self._get_project_key_cache_key(project_key)
                project_id = await self.redis_client.get(cache_key)
                if project_id:
                    project = await self.get_project_by_id(int(project_id), db, use_cache)
                    return project
            except Exception as e:
                logger.warning(f"Failed to get project key mapping from cache: {str(e)}")

        # Query database
        result = await db.execute(select(Project).where(Project.project_key == project_key))
        project = result.scalar_one_or_none()

        if project and use_cache:
            try:
                # Cache project key to project_id mapping
                cache_key = self._get_project_key_cache_key(project_key)
                await self.redis_client.setex(
                    cache_key, settings.CACHE_TTL_PROJECTS, str(project.id)
                )
                # Cache the project
                await self._set_project_in_cache(project.id, project.to_dict())
            except Exception as e:
                logger.warning(f"Failed to set project key mapping in cache: {str(e)}")

        return project

    async def list_projects(
        self,
        db: AsyncSession,
        filters: ProjectFilter | None = None,
        page: int = 1,
        page_size: int = 20,
        use_cache: bool = True,
    ) -> tuple[list[Project], int]:
        """
        List projects with filtering and pagination

        Args:
            filters: Filter criteria
            page: Page number (1-indexed)
            page_size: Number of items per page
            db: Database session
            use_cache: Whether to use cache

        Returns:
            Tuple[List[Project], int]: List of projects and total count
        """
        filters = filters or ProjectFilter()

        # Build filter dictionary for cache key
        filter_dict = filters.model_dump(exclude_unset=True)

        # Try cache first for list results
        if use_cache:
            try:
                cache_key = self._get_list_cache_key(filter_dict, page, page_size)
                cached = await self.redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    # Deserialize cached projects
                    projects = [Project.from_dict(p) for p in data["projects"]]
                    logger.debug("Retrieved project list from cache")
                    return projects, data["total"]
            except Exception as e:
                logger.warning(f"Failed to get project list from cache: {str(e)}")

        # Build query conditions
        conditions = []
        if filters.project_id:
            conditions.append(Project.project_id == filters.project_id)
        if filters.project_key:
            conditions.append(Project.project_key == filters.project_key)
        if filters.is_active is not None:
            conditions.append(Project.is_active == filters.is_active)
        if filters.date_from:
            conditions.append(Project.created_date >= filters.date_from)
        if filters.date_to:
            conditions.append(Project.created_date <= filters.date_to)

        # Get total count
        count_query = select(func.count()).select_from(Project)
        if conditions:
            count_query = count_query.where(and_(*conditions))

        count_result = await db.execute(count_query)
        total = count_result.scalar()

        # Get projects
        query = (
            select(Project)
            .order_by(desc(Project.created_date))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        if conditions:
            query = query.where(and_(*conditions))

        result = await db.execute(query)
        projects = result.scalars().all()

        # Cache the result
        if use_cache and projects:
            try:
                cache_key = self._get_list_cache_key(filter_dict, page, page_size)
                cache_data = {"projects": [p.to_dict() for p in projects], "total": total}
                await self.redis_client.setex(
                    cache_key, settings.CACHE_TTL_PROJECTS, json.dumps(cache_data)
                )
            except Exception as e:
                logger.warning(f"Failed to cache project list: {str(e)}")

        return list(projects), total

    async def update_project(
        self, project_id: int, update_data: ProjectUpdate, db: AsyncSession
    ) -> Project:
        """
        Update a project

        Args:
            project_id: The project database ID
            update_data: The update data
            db: Database session

        Returns:
            Project: The updated project

        Raises:
            ProjectNotFoundException: If the project doesn't exist
        """
        project = await self.get_project_by_id(project_id, db, use_cache=False)
        if not project:
            raise ProjectNotFoundException(project_id=project_id)

        # Update project
        for field, value in update_data.model_dump(exclude_unset=True).items():
            setattr(project, field, value)

        # Invalidate cache
        await self._invalidate_project_cache(project_id, project.project_key)
        await self._invalidate_list_cache()
        await self._invalidate_stats_cache()

        logger.info(f"Updated project: {project.project_id} (ID: {project_id})")
        return project

    async def delete_project(self, project_id: int, db: AsyncSession) -> bool:
        """
        Delete a project

        Args:
            project_id: The project database ID
            db: Database session

        Returns:
            bool: True if deleted, False if not found
        """
        project = await self.get_project_by_id(project_id, db, use_cache=False)
        if not project:
            return False

        await db.delete(project)

        # Invalidate cache
        await self._invalidate_project_cache(project_id, project.project_key)
        await self._invalidate_list_cache()
        await self._invalidate_stats_cache()

        # Update metrics
        self.metrics.decrement_project_count()

        logger.info(f"Deleted project: {project.project_id} (ID: {project_id})")
        return True

    async def get_project_statistics(
        self, db: AsyncSession, project_id: int | None = None, use_cache: bool = True
    ) -> ProjectStats:
        """
        Get project statistics

        Args:
            project_id: Optional project ID to filter statistics
            db: Database session
            use_cache: Whether to use cache

        Returns:
            ProjectStats: Project statistics
        """
        # Try cache first
        cache_key = f"stats:projects:{project_id or 'all'}"
        if use_cache:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    return ProjectStats(**json.loads(cached))
            except Exception as e:
                logger.warning(f"Failed to get project stats from cache: {str(e)}")

        # Build base query
        base_query = select(Project)
        if project_id:
            base_query = base_query.where(Project.id == project_id)

        # Get total projects
        total_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(total_query)
        total_projects = total_result.scalar()

        # Get active projects
        active_query = select(func.count()).select_from(
            base_query.where(Project.is_active == True).subquery()
        )
        active_result = await db.execute(active_query)
        active_projects = active_result.scalar()

        # Get total repositories
        repo_query = select(func.count()).select_from(Repository)
        if project_id:
            repo_query = repo_query.where(Repository.project_id == project_id)
        repo_result = await db.execute(repo_query)
        total_repositories = repo_result.scalar()

        # Get total reviews
        review_query = select(func.count()).select_from(PullRequestReview)
        if project_id:
            review_query = review_query.where(PullRequestReview.project_id == project_id)
        review_result = await db.execute(review_query)
        total_reviews = review_result.scalar()

        # Create statistics object
        stats = ProjectStats(
            total_projects=total_projects,
            active_projects=active_projects,
            total_repositories=total_repositories,
            total_reviews=total_reviews,
        )

        # Cache the result
        if use_cache:
            try:
                await self.redis_client.setex(
                    cache_key, settings.CACHE_TTL_STATS, json.dumps(stats.model_dump())
                )
            except Exception as e:
                logger.warning(f"Failed to cache project stats: {str(e)}")

        return stats

    async def get_active_projects(self, db: AsyncSession, limit: int = 100) -> list[Project]:
        """
        Get active projects

        Args:
            db: Database session
            limit: Maximum number of projects to return

        Returns:
            List[Project]: List of active projects
        """
        result = await db.execute(
            select(Project)
            .where(Project.is_active == True)
            .order_by(Project.created_date)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_project_with_stats(self, project_id: int, db: AsyncSession) -> dict[str, Any]:
        """
        Get a project with its statistics

        Args:
            project_id: The project database ID
            db: Database session

        Returns:
            Dict[str, Any]: Project with statistics

        Raises:
            ProjectNotFoundException: If the project doesn't exist
        """
        project = await self.get_project_by_id(project_id, db, use_cache=False)
        if not project:
            raise ProjectNotFoundException(project_id=project_id)

        # Get project statistics
        stats = await self.get_project_statistics(project_id, db, use_cache=False)

        # Get repository count
        repo_query = (
            select(func.count()).select_from(Repository).where(Repository.project_id == project_id)
        )
        repo_result = await db.execute(repo_query)
        repository_count = repo_result.scalar()

        # Get review count
        review_query = (
            select(func.count())
            .select_from(PullRequestReview)
            .where(PullRequestReview.project_id == project_id)
        )
        review_result = await db.execute(review_query)
        review_count = review_result.scalar()

        # Get active reviewer count
        active_reviewer_query = select(func.count()).select_from(
            select(PullRequestReview.reviewer_id)
            .where(PullRequestReview.project_id == project_id)
            .distinct()
            .subquery()
        )
        active_reviewer_result = await db.execute(active_reviewer_query)
        active_reviewer_count = active_reviewer_result.scalar()

        # Combine results
        project_dict = project.to_dict()
        project_dict.update(
            {
                "repository_count": repository_count,
                "review_count": review_count,
                "active_reviewer_count": active_reviewer_count,
                "statistics": stats.model_dump(),
            }
        )

        return project_dict

    async def activate_project(self, project_id: int, db: AsyncSession) -> Project:
        """
        Activate a project

        Args:
            project_id: The project database ID
            db: Database session

        Returns:
            Project: The updated project

        Raises:
            ProjectNotFoundException: If the project doesn't exist
        """
        project = await self.get_project_by_id(project_id, db, use_cache=False)
        if not project:
            raise ProjectNotFoundException(project_id=project_id)

        if not project.is_active:
            project.is_active = True
            # Invalidate cache
            await self._invalidate_project_cache(project_id, project.project_key)
            await self._invalidate_list_cache()
            await self._invalidate_stats_cache()

            logger.info(f"Activated project: {project.project_id} (ID: {project_id})")

        return project

    async def deactivate_project(self, project_id: int, db: AsyncSession) -> Project:
        """
        Deactivate a project

        Args:
            project_id: The project database ID
            db: Database session

        Returns:
            Project: The updated project

        Raises:
            ProjectNotFoundException: If the project doesn't exist
        """
        project = await self.get_project_by_id(project_id, db, use_cache=False)
        if not project:
            raise ProjectNotFoundException(project_id=project_id)

        if project.is_active:
            project.is_active = False
            # Invalidate cache
            await self._invalidate_project_cache(project_id, project.project_key)
            await self._invalidate_list_cache()
            await self._invalidate_stats_cache()

            logger.info(f"Deactivated project: {project.project_id} (ID: {project_id})")

        return project

    async def get_project_by_name(self, project_name: str, db: AsyncSession) -> Project | None:
        """
        Get a project by name (partial match)

        Args:
            project_name: The project name to search for
            db: Database session

        Returns:
            Project: The project, or None if not found
        """
        result = await db.execute(
            select(Project).where(Project.project_name.ilike(f"%{project_name}%"))
        )
        return result.scalar_one_or_none()

    async def search_projects(
        self,
        db: AsyncSession,
        search_term: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Project], int]:
        """
        Search projects by name, ID, or key

        Args:
            search_term: The search term
            page: Page number (1-indexed)
            page_size: Number of items per page
            db: Database session

        Returns:
            Tuple[List[Project], int]: List of projects and total count
        """
        # Build search conditions
        search_term_pattern = f"%{search_term}%"
        conditions = or_(
            Project.project_name.ilike(search_term_pattern),
            Project.project_id.ilike(search_term_pattern),
            Project.project_key.ilike(search_term_pattern),
        )

        # Get total count
        count_query = select(func.count()).select_from(Project).where(conditions)
        count_result = await db.execute(count_query)
        total = count_result.scalar()

        # Get projects
        query = (
            select(Project)
            .where(conditions)
            .order_by(desc(Project.created_date))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )

        result = await db.execute(query)
        projects = result.scalars().all()

        return list(projects), total

    async def get_project_repository_count(
        self, project_id: int, db: AsyncSession, use_cache: bool = True
    ) -> int:
        """
        Get the number of repositories in a project

        Args:
            project_id: The project database ID
            db: Database session
            use_cache: Whether to use cache

        Returns:
            int: Number of repositories
        """
        # Try cache first
        cache_key = f"project:{project_id}:repo_count"
        if use_cache:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    return int(cached)
            except Exception as e:
                logger.warning(f"Failed to get repo count from cache: {str(e)}")

        # Query database
        query = (
            select(func.count()).select_from(Repository).where(Repository.project_id == project_id)
        )
        result = await db.execute(query)
        count = result.scalar()

        # Cache the result
        if use_cache:
            try:
                await self.redis_client.setex(cache_key, settings.CACHE_TTL_PROJECTS, str(count))
            except Exception as e:
                logger.warning(f"Failed to cache repo count: {str(e)}")

        return count

    async def get_project_review_count(
        self, project_id: int, db: AsyncSession, use_cache: bool = True
    ) -> int:
        """
        Get the number of reviews in a project

        Args:
            project_id: The project database ID
            db: Database session
            use_cache: Whether to use cache

        Returns:
            int: Number of reviews
        """
        # Try cache first
        cache_key = f"project:{project_id}:review_count"
        if use_cache:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    return int(cached)
            except Exception as e:
                logger.warning(f"Failed to get review count from cache: {str(e)}")

        # Query database
        query = (
            select(func.count())
            .select_from(PullRequestReview)
            .where(PullRequestReview.project_id == project_id)
        )
        result = await db.execute(query)
        count = result.scalar()

        # Cache the result
        if use_cache:
            try:
                await self.redis_client.setex(cache_key, settings.CACHE_TTL_PROJECTS, str(count))
            except Exception as e:
                logger.warning(f"Failed to cache review count: {str(e)}")

        return count

    async def get_project_active_reviewer_count(
        self, project_id: int, db: AsyncSession, use_cache: bool = True
    ) -> int:
        """
        Get the number of active reviewers in a project

        Args:
            project_id: The project database ID
            db: Database session
            use_cache: Whether to use cache

        Returns:
            int: Number of active reviewers
        """
        # Try cache first
        cache_key = f"project:{project_id}:active_reviewer_count"
        if use_cache:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    return int(cached)
            except Exception as e:
                logger.warning(f"Failed to get active reviewer count from cache: {str(e)}")

        # Query database
        query = select(func.count()).select_from(
            select(PullRequestReview.reviewer_id)
            .where(PullRequestReview.project_id == project_id)
            .distinct()
            .subquery()
        )
        result = await db.execute(query)
        count = result.scalar()

        # Cache the result
        if use_cache:
            try:
                await self.redis_client.setex(cache_key, settings.CACHE_TTL_PROJECTS, str(count))
            except Exception as e:
                logger.warning(f"Failed to cache active reviewer count: {str(e)}")

        return count

    async def get_projects_with_most_reviews(
        self, db: AsyncSession, limit: int = 10, days: int = 30
    ) -> list[dict[str, Any]]:
        """
        Get projects with the most reviews in a given time period

        Args:
            db: Database session
            limit: Maximum number of projects to return
            days: Number of days to look back

        Returns:
            List[Dict[str, Any]]: List of projects with review counts
        """
        # Calculate date threshold
        date_threshold = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        date_threshold = (
            date_threshold.replace(day=date_threshold.day - days)
            if date_threshold.day > days
            else date_threshold.replace(day=1)
        )

        # Query projects with review counts
        query = (
            select(
                Project.id,
                Project.project_id,
                Project.project_name,
                func.count(PullRequestReview.id).label("review_count"),
            )
            .join(PullRequestReview, Project.id == PullRequestReview.project_id)
            .where(PullRequestReview.created_date >= date_threshold)
            .group_by(Project.id)
            .order_by(desc("review_count"))
            .limit(limit)
        )

        result = await db.execute(query)
        projects = []
        for row in result:
            projects.append(
                {
                    "id": row.id,
                    "project_id": row.project_id,
                    "project_name": row.project_name,
                    "review_count": row.review_count,
                }
            )

        return projects

    async def get_projects_with_most_active_reviewers(
        self, db: AsyncSession, limit: int = 10, days: int = 30
    ) -> list[dict[str, Any]]:
        """
        Get projects with the most active reviewers in a given time period

        Args:
            db: Database session
            limit: Maximum number of projects to return
            days: Number of days to look back

        Returns:
            List[Dict[str, Any]]: List of projects with active reviewer counts
        """
        # Calculate date threshold
        date_threshold = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        date_threshold = (
            date_threshold.replace(day=date_threshold.day - days)
            if date_threshold.day > days
            else date_threshold.replace(day=1)
        )

        # Query projects with active reviewer counts
        query = (
            select(
                Project.id,
                Project.project_id,
                Project.project_name,
                func.count(func.distinct(PullRequestReview.reviewer_id)).label(
                    "active_reviewer_count"
                ),
            )
            .join(PullRequestReview, Project.id == PullRequestReview.project_id)
            .where(PullRequestReview.created_date >= date_threshold)
            .group_by(Project.id)
            .order_by(desc("active_reviewer_count"))
            .limit(limit)
        )

        result = await db.execute(query)
        projects = []
        for row in result:
            projects.append(
                {
                    "id": row.id,
                    "project_id": row.project_id,
                    "project_name": row.project_name,
                    "active_reviewer_count": row.active_reviewer_count,
                }
            )

        return projects

    async def invalidate_project_cache(
        self, project_id: int, project_key: str | None = None
    ) -> None:
        """
        Invalidate cache for a specific project

        Args:
            project_id: The project database ID
            project_key: Optional project key
        """
        if project_key:
            await self._invalidate_project_cache(project_id, project_key)
        else:
            try:
                await self.redis_client.delete(self._get_cache_key(project_id))
            except Exception as e:
                logger.warning(f"Failed to invalidate project cache: {str(e)}")
