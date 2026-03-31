"""Entity Synchronization Service

This service handles automatic synchronization of related entities (Project, Repository, User)
when inserting PR reviews. It queries existing records and fetches from Bitbucket API if needed.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.project import Project
from src.models.repository import Repository
from src.models.user import User
from src.services.bitbucket_service import get_bitbucket_service


logger = logging.getLogger(__name__)


class EntitySyncService:
    """Service for synchronizing entities from Bitbucket API"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.bitbucket = get_bitbucket_service()

    async def sync_project(self, project_key: str) -> Project:
        """
        Sync project entity - query first, then fetch from API if not exists

        Args:
            project_key: The project key to sync

        Returns:
            Project instance (either existing or newly created)
        """
        # Try to find existing project
        project_result = await self.db.execute(
            select(Project).where(Project.project_key == project_key)
        )
        project = project_result.scalar_one_or_none()

        if project:
            logger.debug(f"Project already exists: {project_key}")
            return project

        # Fetch from Bitbucket API
        logger.info(f"Project not found, fetching from Bitbucket: {project_key}")
        project_info = await self.bitbucket.get_project_info(project_key)

        if not project_info:
            raise ValueError(f"Failed to fetch project info for {project_key}")

        # Create new project
        project = Project(
            project_id=project_info["project_id"],
            project_name=project_info["project_name"],
            project_key=project_info["project_key"],
            project_url=project_info["project_url"],
        )
        self.db.add(project)
        await self.db.flush()

        logger.info(f"Created project from Bitbucket API: {project_key}")
        return project

    async def sync_repository(
        self,
        repository_slug: str,
        project: Project,
    ) -> Repository:
        """
        Sync repository entity - query first, then fetch from API if not exists

        Args:
            repository_slug: The repository slug to sync
            project: Parent project instance

        Returns:
            Repository instance (either existing or newly created)
        """
        # Try to find existing repository - must query by both project_id and repository_slug
        repo_result = await self.db.execute(
            select(Repository).where(
                Repository.project_id == project.project_id,
                Repository.repository_slug == repository_slug,
            )
        )
        repository = repo_result.scalar_one_or_none()

        if repository:
            logger.debug(
                f"Repository already exists: {repository_slug} under project {project.project_key}"
            )
            return repository

        # Fetch from Bitbucket API using project_key as workspace
        logger.info(
            f"Repository not found, fetching from Bitbucket: {project.project_key}/{repository_slug}"
        )
        repo_info = await self.bitbucket.get_repository_info(project.project_key, repository_slug)

        if not repo_info:
            raise ValueError(f"Failed to fetch repository info for {repository_slug}")

        # Create new repository
        repository = Repository(
            repository_id=repo_info["repository_id"],
            project_id=project.project_id,
            repository_name=repo_info["repository_name"],
            repository_slug=repository_slug,
            repository_url=repo_info["repository_url"],
        )
        self.db.add(repository)
        await self.db.flush()

        logger.info(f"Created repository from Bitbucket API: {repository_slug}")
        return repository

    async def sync_user(self, username: str, is_reviewer: bool = False) -> User:
        """
        Sync user entity - query first, then fetch from API if not exists

        Args:
            username: The username to sync
            is_reviewer: Whether this user is a reviewer

        Returns:
            User instance (either existing or newly created)
        """
        # Try to find existing user
        user_result = await self.db.execute(select(User).where(User.username == username))
        user = user_result.scalar_one_or_none()

        if user:
            logger.debug(f"User already exists: {username}")
            # Update reviewer status if needed
            if is_reviewer and not user.is_reviewer:
                user.is_reviewer = True
                await self.db.flush()
            return user

        # Fetch from Bitbucket API
        logger.info(f"User not found, fetching from Bitbucket: {username}")
        user_info = await self.bitbucket.get_user_info(username)

        if not user_info:
            raise ValueError(f"Failed to fetch user info for {username}")

        # Create new user
        user = User(
            user_id=user_info["user_id"],
            username=username,
            display_name=user_info["display_name"],
            email_address=user_info["email_address"],
            active=True,
            is_reviewer=is_reviewer,
        )
        self.db.add(user)
        await self.db.flush()

        logger.info(f"Created user from Bitbucket API: {username}")
        return user

    async def sync_all_entities(
        self,
        project_key: str,
        repository_slug: str,
        reviewer: str,
        pull_request_user: str,
    ) -> tuple[Project, Repository, User, User]:
        """
        Sync all related entities at once

        Args:
            project_key: Project key
            repository_slug: Repository slug
            reviewer: Reviewer username
            pull_request_user: PR author username

        Returns:
            Tuple of (Project, Repository, User, User) in order
        """
        # Sync in order: Project -> Repository -> Users
        project = await self.sync_project(project_key)
        repository = await self.sync_repository(repository_slug, project)
        pr_user = await self.sync_user(pull_request_user, is_reviewer=False)
        reviewer_user = await self.sync_user(reviewer, is_reviewer=True)

        return project, repository, pr_user, reviewer_user
