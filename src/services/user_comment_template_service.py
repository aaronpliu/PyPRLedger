"""Service for managing personalized user comment templates"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AppException, ErrorCode
from src.models.user_comment_template import UserCommentTemplate


logger = logging.getLogger(__name__)

# Constants
MAX_TEMPLATES_PER_USER = 200


class UserCommentTemplateService:
    """Service for managing personalized user comment templates"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_templates(self, auth_user_id: int) -> list[UserCommentTemplate]:
        """List templates owned by a user (most recently updated first)"""
        result = await self.db.execute(
            select(UserCommentTemplate)
            .where(UserCommentTemplate.auth_user_id == auth_user_id)
            .order_by(UserCommentTemplate.updated_at.desc(), UserCommentTemplate.id.desc())
        )
        return result.scalars().all()

    async def create_template(
        self,
        auth_user_id: int,
        name: str,
        content: str,
    ) -> UserCommentTemplate:
        """Create a new personal comment template for a user"""
        count = await self.get_template_count(auth_user_id)
        if count >= MAX_TEMPLATES_PER_USER:
            raise AppException(
                error_code=ErrorCode.VALIDATION_ERROR,
                message=f"Maximum {MAX_TEMPLATES_PER_USER} comment templates allowed per user.",
            )

        template_record = UserCommentTemplate(
            auth_user_id=auth_user_id,
            name=name.strip(),
            content=content,
        )

        self.db.add(template_record)
        await self.db.commit()
        await self.db.refresh(template_record)

        logger.info(
            "User comment template created",
            extra={"template_id": template_record.id, "user_id": auth_user_id},
        )

        return template_record

    async def update_template(
        self,
        auth_user_id: int,
        template_id: int,
        name: str | None = None,
        content: str | None = None,
    ) -> UserCommentTemplate | None:
        """Update an existing personal comment template (verify ownership)

        Returns:
            Updated template if found and owned by the user, None otherwise
        """
        result = await self.db.execute(
            select(UserCommentTemplate)
            .where(UserCommentTemplate.id == template_id)
            .where(UserCommentTemplate.auth_user_id == auth_user_id)
        )
        template_record = result.scalar_one_or_none()

        if not template_record:
            return None

        if name is not None:
            template_record.name = name.strip()
        if content is not None:
            template_record.content = content

        await self.db.commit()
        await self.db.refresh(template_record)

        logger.info(
            "User comment template updated",
            extra={"template_id": template_id, "user_id": auth_user_id},
        )

        return template_record

    async def delete_template(self, auth_user_id: int, template_id: int) -> bool:
        """Delete a personal comment template (verify ownership)"""
        result = await self.db.execute(
            select(UserCommentTemplate)
            .where(UserCommentTemplate.id == template_id)
            .where(UserCommentTemplate.auth_user_id == auth_user_id)
        )
        template_record = result.scalar_one_or_none()

        if not template_record:
            return False

        await self.db.delete(template_record)
        await self.db.commit()

        logger.info(
            "User comment template deleted",
            extra={"template_id": template_id, "user_id": auth_user_id},
        )

        return True

    async def get_template_count(self, auth_user_id: int) -> int:
        """Count templates owned by a user"""
        result = await self.db.execute(
            select(UserCommentTemplate).where(UserCommentTemplate.auth_user_id == auth_user_id)
        )
        return len(result.scalars().all())
