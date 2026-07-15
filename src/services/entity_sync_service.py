"""Entity Synchronization Service

This service handles automatic synchronization of related entities (Project, Repository, User)
when inserting PR reviews. It queries existing records and fetches from Git provider API if needed.
Supports multiple providers (Bitbucket Server, GitHub Enterprise) via provider abstraction.
"""

from __future__ import annotations

import logging

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.git_provider import GitProvider
from src.models.project import Project
from src.models.project_registry import ProjectRegistry
from src.models.repository import Repository
from src.models.user import User
from src.services.git_providers import BaseGitProvider, get_git_provider


logger = logging.getLogger(__name__)


class EntitySyncService:
    """Service for synchronizing entities from Git provider API.

    Provider resolution (hybrid strategy):
    1. Check project_registry for (project_key, repository_slug) -> use registered provider
    2. Fall back to git_provider hint from payload (if provided)
    3. Default to bitbucket_server (preserves existing behavior)
    """

    def __init__(self, db: AsyncSession, git_provider: str | GitProvider | None = None):
        self.db = db
        self._provider: BaseGitProvider | None = None
        self._payload_hint: str | None = (
            git_provider.value if isinstance(git_provider, GitProvider) else git_provider
        )

    async def _resolve_provider(self) -> BaseGitProvider:
        """Lazy-resolve provider on first use, then memoize for the session."""
        if self._provider is not None:
            return self._provider
        await self._try_resolve_provider_from_registry(None, None)
        if self._provider is None:
            if self._payload_hint:
                if GitProvider.is_valid(self._payload_hint):
                    self._provider = get_git_provider(self._payload_hint)
                else:
                    logger.warning(
                        f"Invalid git_provider hint '{self._payload_hint}', "
                        f"falling back to {GitProvider.default()}"
                    )
                    self._provider = get_git_provider(GitProvider.default())
            else:
                self._provider = get_git_provider(GitProvider.default())
        return self._provider

    async def _try_resolve_provider_from_registry(
        self, project_key: str | None, repository_slug: str | None
    ) -> None:
        """Try to determine provider from project_registry (best effort)."""
        if not project_key or not repository_slug:
            return
        try:
            result = await self.db.execute(
                select(ProjectRegistry).where(
                    and_(
                        ProjectRegistry.project_key == project_key,
                        ProjectRegistry.repository_slug == repository_slug,
                    )
                )
            )
            entry = result.scalar_one_or_none()
            if entry:
                try:
                    self._provider = get_git_provider(entry.git_provider)
                    logger.debug(
                        f"Resolved provider '{entry.git_provider}' from registry "
                        f"for {project_key}/{repository_slug}"
                    )
                except ValueError:
                    logger.warning(
                        f"Registry entry for {project_key}/{repository_slug} has "
                        f"invalid git_provider '{entry.git_provider}', skipping"
                    )
        except Exception:
            pass

    async def sync_project(self, project_key: str) -> Project:
        """
        Sync project entity - query first, then fetch from API if not exists

        Args:
            project_key: The project key to sync

        Returns:
            Project instance (either existing or newly created)
        """
        project_result = await self.db.execute(
            select(Project).where(Project.project_key == project_key)
        )
        project = project_result.scalar_one_or_none()

        if project:
            logger.debug(f"Project already exists: {project_key}")
            return project

        provider = await self._resolve_provider()
        logger.info(f"Project not found, fetching from {provider.name}: {project_key}")
        project_info = await provider.get_project_info(project_key)

        if not project_info:
            raise ValueError(f"Failed to fetch project info for {project_key}")

        project = Project(
            project_id=project_info["project_id"],
            project_name=project_info["project_name"],
            project_key=project_info["project_key"],
            project_url=project_info["project_url"],
            git_provider=provider.name,
        )
        self.db.add(project)
        await self.db.flush()

        logger.info(f"Created project from {provider.name} API: {project_key}")
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

        await self._try_resolve_provider_from_registry(project.project_key, repository_slug)
        provider = await self._resolve_provider()
        logger.info(
            f"Repository not found, fetching from {provider.name}: "
            f"{project.project_key}/{repository_slug}"
        )
        repo_info = await provider.get_repository_info(project.project_key, repository_slug)

        if not repo_info:
            raise ValueError(f"Failed to fetch repository info for {repository_slug}")

        repository = Repository(
            repository_id=repo_info["repository_id"],
            project_id=project.project_id,
            repository_name=repo_info["repository_name"],
            repository_slug=repository_slug,
            repository_url=repo_info["repository_url"],
        )
        self.db.add(repository)
        await self.db.flush()

        logger.info(f"Created repository from {provider.name} API: {repository_slug}")
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
        user_result = await self.db.execute(select(User).where(User.username == username))
        user = user_result.scalar_one_or_none()

        if user:
            logger.debug(f"User already exists: {username}")
            if is_reviewer and not user.is_reviewer:
                user.is_reviewer = True
                await self.db.flush()
                await self._upgrade_linked_auth_user_role(user)
            return user

        provider = await self._resolve_provider()
        logger.info(f"User not found, fetching from {provider.name}: {username}")
        user_info = await provider.get_user_info(username)

        if not user_info:
            raise ValueError(f"Failed to fetch user info for {username}")

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

        logger.info(f"Created user from {provider.name} API: {username}")

        await self._auto_associate_auth_user(user)
        await self._invalidate_user_list_cache()

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

        # Auto-set is_reviewer=1 when auth user binds to git user
        if not git_user.is_reviewer:
            git_user.is_reviewer = True
            logger.info(f"Auto-set is_reviewer=True for git user {git_user.username}")

        await self.db.flush()

        logger.info(f"Auto-associated auth_user {auth_user.id} with Bitbucket user {git_user.id}")

        # Log audit trail
        await self._log_association_audit(auth_user.id, git_user.id, git_user.username)

        # Upgrade role from viewer to reviewer
        await self._upgrade_role_to_reviewer(auth_user.id)

    async def _upgrade_linked_auth_user_role(self, git_user: User) -> None:
        """Upgrade auth_user role to reviewer when git user is marked as reviewer

        This handles the scenario where a PR review is inserted with a specified reviewer.
        If the git user has a linked auth_user, upgrade their role to 'reviewer'.

        Args:
            git_user: The git user who is now a reviewer
        """
        from src.models.auth_user import AuthUser

        # Find auth_user linked to this git user
        stmt = select(AuthUser).where(AuthUser.user_id == git_user.id)
        result = await self.db.execute(stmt)
        auth_user = result.scalar_one_or_none()

        if not auth_user:
            logger.debug(
                f"No auth_user linked to git user {git_user.username}, skipping role upgrade"
            )
            return

        logger.info(
            f"Git user {git_user.username} (ID: {git_user.id}) is now a reviewer. "
            f"Upgrading linked auth_user {auth_user.id} to reviewer role."
        )

        # Upgrade the role
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

    async def _invalidate_user_list_cache(self) -> None:
        """Invalidate user list cache when users are created or updated"""
        try:
            from src.core.redis_client import get_redis_client

            redis_client = get_redis_client()
            keys = await redis_client.keys("users:list:*")
            if keys:
                await redis_client.delete(*keys)
                logger.debug(f"Invalidated {len(keys)} user list cache entries")
        except Exception as e:
            logger.warning(f"Failed to invalidate user list cache: {str(e)}")
