"""Visibility grants: which repositories a subject is allowed to see."""

from __future__ import annotations

import logging

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundException, ValidationException
from src.models.auth_user import AuthUser
from src.models.project import Project
from src.models.project_registry import ProjectRegistry
from src.models.repository import Repository
from src.models.user import User
from src.models.user_repository_access import (
    SUBJECT_AUTH_USER,
    SUBJECT_GIT_USER,
    VALID_SUBJECT_TYPES,
    UserRepositoryAccess,
)
from src.utils.timezone import get_current_time


logger = logging.getLogger(__name__)


class RepositoryAccessService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def allowed_pairs(self, auth_user_id: int) -> set[tuple[str, str]]:
        """Repositories visible to a logged-in user.

        A system user sees the union of its own grants and the grants of the git
        user it is linked to. No role is consulted here.
        """
        linked = await self.db.execute(
            select(AuthUser.user_id).where(AuthUser.id == auth_user_id)
        )
        git_user_id = linked.scalar_one_or_none()

        conditions = [
            and_(
                UserRepositoryAccess.subject_type == SUBJECT_AUTH_USER,
                UserRepositoryAccess.subject_id == auth_user_id,
            )
        ]
        if git_user_id is not None:
            conditions.append(
                and_(
                    UserRepositoryAccess.subject_type == SUBJECT_GIT_USER,
                    UserRepositoryAccess.subject_id == git_user_id,
                )
            )

        rows = await self.db.execute(
            select(
                UserRepositoryAccess.project_key,
                UserRepositoryAccess.repository_slug,
            ).where(or_(*conditions))
        )
        return {(row[0], row[1]) for row in rows.all()}

    async def resolve_subject(self, subject_type: str, subject_id: int) -> str:
        """Validate the subject and return its username."""
        if subject_type not in VALID_SUBJECT_TYPES:
            raise ValidationException(message=f"Unknown subject type: {subject_type}")

        if subject_type == SUBJECT_AUTH_USER:
            result = await self.db.execute(select(AuthUser).where(AuthUser.id == subject_id))
            subject = result.scalar_one_or_none()
        else:
            result = await self.db.execute(select(User).where(User.id == subject_id))
            subject = result.scalar_one_or_none()

        if subject is None:
            raise NotFoundException(message=f"Subject {subject_type}:{subject_id} not found")
        return subject.username

    async def list_access(self, subject_type: str, subject_id: int) -> list[dict]:
        result = await self.db.execute(
            select(UserRepositoryAccess)
            .where(
                UserRepositoryAccess.subject_type == subject_type,
                UserRepositoryAccess.subject_id == subject_id,
            )
            .order_by(
                UserRepositoryAccess.project_key,
                UserRepositoryAccess.repository_slug,
            )
        )
        return [row.to_dict() for row in result.scalars().all()]

    async def replace_access(
        self,
        subject_type: str,
        subject_id: int,
        pairs: set[tuple[str, str]],
        granted_by: int | None,
    ) -> list[dict]:
        """Replace the complete grant list of one subject inside one transaction."""
        username = await self.resolve_subject(subject_type, subject_id)
        catalog = await self.list_catalog()
        known = {(item["project_key"], item["repository_slug"]) for item in catalog}
        unknown = sorted(pairs - known)
        if unknown:
            raise ValidationException(message=f"Unknown repositories: {unknown[:10]}")

        await self.db.execute(
            delete(UserRepositoryAccess).where(
                UserRepositoryAccess.subject_type == subject_type,
                UserRepositoryAccess.subject_id == subject_id,
            )
        )

        now = get_current_time()
        for project_key, repository_slug in sorted(pairs):
            self.db.add(
                UserRepositoryAccess(
                    subject_type=subject_type,
                    subject_id=subject_id,
                    subject_username=username,
                    project_key=project_key,
                    repository_slug=repository_slug,
                    granted_by=granted_by,
                    created_at=now,
                    updated_at=now,
                )
            )

        await self.db.commit()
        logger.info(
            "Repository access replaced",
            extra={
                "subject_type": subject_type,
                "subject_id": subject_id,
                "granted_by": granted_by,
                "granted_repositories": len(pairs),
            },
        )
        return await self.list_access(subject_type, subject_id)

    async def ensure_author_grants(
        self, project_key: str, repository_slug: str, username: str | None
    ) -> None:
        """Grant a PR author its repository, together with any linked system user.

        Runs inside the caller's transaction and never commits, so the grant is
        rolled back together with the review if the insert fails.
        """
        if not username:
            return

        result = await self.db.execute(select(User).where(User.username == username))
        git_user = result.scalar_one_or_none()
        if git_user is None:
            return

        subjects = [(SUBJECT_GIT_USER, git_user.id)]
        linked = await self.db.execute(select(AuthUser).where(AuthUser.user_id == git_user.id))
        subjects.extend((SUBJECT_AUTH_USER, row.id) for row in linked.scalars().all())

        now = get_current_time()
        for subject_type, subject_id in subjects:
            existing = await self.db.execute(
                select(UserRepositoryAccess.id)
                .where(
                    UserRepositoryAccess.subject_type == subject_type,
                    UserRepositoryAccess.subject_id == subject_id,
                    UserRepositoryAccess.project_key == project_key,
                    UserRepositoryAccess.repository_slug == repository_slug,
                )
                .limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                continue

            self.db.add(
                UserRepositoryAccess(
                    subject_type=subject_type,
                    subject_id=subject_id,
                    subject_username=git_user.username,
                    project_key=project_key,
                    repository_slug=repository_slug,
                    granted_by=None,
                    created_at=now,
                    updated_at=now,
                )
            )

    async def list_catalog(self) -> list[dict]:
        """Every known repository pair, without business data."""
        entries: dict[tuple[str, str], dict] = {}

        registered = await self.db.execute(
            select(
                ProjectRegistry.project_key,
                ProjectRegistry.repository_slug,
                ProjectRegistry.app_name,
            )
        )
        for project_key, repository_slug, app_name in registered.all():
            entries[(project_key, repository_slug)] = {
                "project_key": project_key,
                "repository_slug": repository_slug,
                "app_name": app_name,
            }

        synced = await self.db.execute(
            select(Project.project_key, Repository.repository_slug).join(
                Repository, Repository.project_id == Project.project_id
            )
        )
        for project_key, repository_slug in synced.all():
            entries.setdefault(
                (project_key, repository_slug),
                {
                    "project_key": project_key,
                    "repository_slug": repository_slug,
                    "app_name": None,
                },
            )

        return sorted(
            entries.values(), key=lambda item: (item["project_key"], item["repository_slug"])
        )
