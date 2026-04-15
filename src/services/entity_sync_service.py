"""Entity Synchronization Service

This service handles automatic synchronization of related entities (Project, Repository, User)
when inserting PR reviews. It queries existing records and fetches from Bitbucket API if needed.
"""

import logging

from sqlalchemy import and_, select
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

        # Auto-associate with auth_user if exists
        await self._auto_associate_auth_user(user)

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

    async def _auto_associate_auth_user(self, git_user: User) -> None:
        """Auto-associate auth_user when Bitbucket user is created

        If an auth_user exists with the same username but no user_id link,
        create the link and upgrade role from 'viewer' to 'reviewer'.

        Args:
            git_user: The newly created or synced Bitbucket user
        """
        from src.models.auth_user import AuthUser

        # Find auth_user with same username but no link
        stmt = select(AuthUser).where(
            and_(
                AuthUser.username == git_user.username,
                AuthUser.user_id.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        auth_user = result.scalar_one_or_none()

        if not auth_user:
            logger.debug(f"No unlinked auth_user found for {git_user.username}")
            return

        # Create the association
        auth_user.user_id = git_user.id
        await self.db.flush()

        logger.info(f"Auto-associated auth_user {auth_user.id} with Bitbucket user {git_user.id}")

        # Log audit trail
        await self._log_association_audit(auth_user.id, git_user.id, git_user.username)

        # Upgrade role from viewer to reviewer
        await self._upgrade_role_to_reviewer(auth_user.id)

    async def _upgrade_role_to_reviewer(self, auth_user_id: int) -> None:
        """Upgrade user role from viewer to reviewer after Bitbucket user association

        Only upgrades if the user currently has 'viewer' role and doesn't have higher roles.
        This prevents downgrading users who may have been manually assigned admin roles.

        Args:
            auth_user_id: The auth user ID to upgrade
        """
        from src.models.rbac import UserRoleAssignment
        from src.models.role import Role
        from src.services.rbac_service import RBACService

        rbac_service = RBACService(self.db)

        # Get viewer and reviewer roles
        stmt = select(Role).where(Role.name.in_(["viewer", "reviewer"]))
        result = await self.db.execute(stmt)
        roles = {r.name: r for r in result.scalars().all()}

        viewer_role = roles.get("viewer")
        reviewer_role = roles.get("reviewer")

        if not viewer_role or not reviewer_role:
            logger.warning("Viewer or reviewer role not found, skipping upgrade")
            return

        # Check current roles of the user
        stmt = (
            select(UserRoleAssignment, Role)
            .join(Role, UserRoleAssignment.role_id == Role.id)
            .where(
                and_(
                    UserRoleAssignment.auth_user_id == auth_user_id,
                    UserRoleAssignment.resource_type == "global",
                )
            )
        )
        result = await self.db.execute(stmt)
        current_assignments = result.all()

        # Extract role names
        current_role_names = {role.name for _, role in current_assignments}

        # Safety check: Don't downgrade if user has admin roles
        admin_roles = {"review_admin", "system_admin"}
        if current_role_names & admin_roles:
            logger.info(
                f"User {auth_user_id} has admin roles {current_role_names & admin_roles}, "
                f"skipping auto-upgrade to avoid permission conflicts"
            )
            return

        # Check if already has reviewer role
        if "reviewer" in current_role_names:
            logger.info(f"User {auth_user_id} already has reviewer role")
            # Remove redundant viewer role if exists
            if "viewer" in current_role_names:
                viewer_assignment = next(
                    (
                        assignment
                        for assignment, role in current_assignments
                        if role.name == "viewer"
                    ),
                    None,
                )
                if viewer_assignment:
                    await self.db.delete(viewer_assignment)
                    await self.db.commit()
                    logger.info(f"Removed redundant viewer role from user {auth_user_id}")
            return

        # Check if has viewer role
        viewer_assignment = next(
            (assignment for assignment, role in current_assignments if role.name == "viewer"),
            None,
        )

        if not viewer_assignment:
            logger.debug(f"User {auth_user_id} doesn't have viewer role, assigning reviewer")

        try:
            # Remove viewer role if exists
            if viewer_assignment:
                await self.db.delete(viewer_assignment)

            # Assign reviewer role
            await rbac_service.assign_role(
                auth_user_id=auth_user_id,
                role_id=reviewer_role.id,
                resource_type="global",
                resource_id=None,
                granted_by=None,  # System assigned
            )
            await self.db.commit()

            logger.info(f"Upgraded user {auth_user_id} from viewer to reviewer role")

            # Log audit trail for role upgrade
            await self._log_role_upgrade_audit(auth_user_id)
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to upgrade role for user {auth_user_id}: {e}")

    async def _log_association_audit(
        self, auth_user_id: int, git_user_id: int, username: str
    ) -> None:
        """Log audit trail for automatic user association

        Args:
            auth_user_id: The auth user ID
            git_user_id: The Bitbucket user ID
            username: The username
        """
        try:
            from src.services.audit_service import AuditService

            audit_service = AuditService(self.db)
            await audit_service.log_action(
                auth_user_id=None,  # System action, no specific user
                action="auto_associate_user",
                resource_type="users",
                resource_id=str(auth_user_id),
                new_values={
                    "auth_user_id": auth_user_id,
                    "git_user_id": git_user_id,
                    "username": username,
                    "action": "auto_associated",
                },
            )
        except Exception as e:
            logger.warning(f"Failed to log association audit: {e}")

    async def _log_role_upgrade_audit(self, auth_user_id: int) -> None:
        """Log audit trail for role upgrade

        Args:
            auth_user_id: The auth user ID that was upgraded
        """
        try:
            from src.services.audit_service import AuditService

            audit_service = AuditService(self.db)
            await audit_service.log_action(
                auth_user_id=None,  # System action
                action="auto_upgrade_role",
                resource_type="users",
                resource_id=str(auth_user_id),
                old_values={"role": "viewer"},
                new_values={"role": "reviewer", "reason": "git_user_associated"},
            )
        except Exception as e:
            logger.warning(f"Failed to log role upgrade audit: {e}")
