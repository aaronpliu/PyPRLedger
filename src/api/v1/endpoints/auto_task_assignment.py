"""API endpoints for auto-assignment rule management (review_admin only)"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.models.auto_assign_rule import PullRequestReviewAutoAssignmentRule
from src.models.user import User
from src.schemas.auto_assign_rule import (
    AutoAssignRuleCreate,
    AutoAssignRuleListResponse,
    AutoAssignRuleResponse,
    AutoAssignRuleToggleResponse,
    AutoAssignRuleUpdate,
)
from src.services.rbac_service import RBACService
from src.utils.timezone import get_current_time


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auto-task-assignment", tags=["auto-task-assignment"])


async def _get_git_username(auth_user_id: int, db: AsyncSession) -> str | None:
    """Get the Git username associated with an auth user"""
    stmt = select(AuthUser).where(AuthUser.id == auth_user_id)
    result = await db.execute(stmt)
    auth_user = result.scalar_one_or_none()

    if not auth_user or not auth_user.user_id:
        return None

    stmt = select(User).where(User.id == auth_user.user_id)
    result = await db.execute(stmt)
    git_user = result.scalar_one_or_none()
    return git_user.username if git_user else None


async def _require_assign_permission(
    current_user: AuthUser,
    db: AsyncSession,
) -> str:
    """Check that current user has assign permission and return their git username

    Raises:
        HTTPException 403 if missing permission
        HTTPException 400 if no linked git account
    """
    rbac_service = RBACService(db)
    has_permission = await rbac_service.check_permission(
        auth_user_id=current_user.id,
        action="assign",
        resource_type="reviews",
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "FORBIDDEN",
                "message": "You do not have permission to manage auto-assignment rules. Requires 'review_admin' role or higher.",
            },
        )

    git_username = await _get_git_username(current_user.id, db)
    if not git_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "BAD_REQUEST",
                "message": f"User '{current_user.username}' does not have an associated Git account. "
                f"A Git account is required to manage auto-assignment rules.",
            },
        )
    return git_username


@router.post("/rules", response_model=AutoAssignRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    rule_data: AutoAssignRuleCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> AutoAssignRuleResponse:
    """Create a new auto-assignment rule

    Requires 'assign' permission on 'reviews' (review_admin role or higher).
    """
    git_username = await _require_assign_permission(current_user, db)

    now = get_current_time()
    rule = PullRequestReviewAutoAssignmentRule(
        name=rule_data.name,
        description=rule_data.description,
        priority=rule_data.priority,
        conditions=rule_data.conditions,
        assign_to=rule_data.assign_to,
        max_assignments=rule_data.max_assignments,
        starts_at=rule_data.starts_at,
        expires_at=rule_data.expires_at,
        is_active=rule_data.is_active,
        created_by=git_username,
        created_at=now,
        updated_at=now,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)

    logger.info(
        "Auto-assign rule created",
        extra={
            "rule_id": rule.id,
            "rule_name": rule.name,
            "created_by": git_username,
        },
    )

    return AutoAssignRuleResponse.model_validate(rule)


@router.get("/rules", response_model=AutoAssignRuleListResponse)
async def list_rules(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> AutoAssignRuleListResponse:
    """List all auto-assignment rules ordered by priority

    Requires 'assign' permission on 'reviews' (review_admin role or higher).
    """
    await _require_assign_permission(current_user, db)

    # Get total count
    count_stmt = select(PullRequestReviewAutoAssignmentRule)
    total_result = await db.execute(count_stmt)
    total = len(list(total_result.scalars().all()))

    # Get paginated results ordered by priority
    stmt = (
        select(PullRequestReviewAutoAssignmentRule)
        .order_by(PullRequestReviewAutoAssignmentRule.priority)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    rules = result.scalars().all()

    items = [AutoAssignRuleResponse.model_validate(rule) for rule in rules]

    return AutoAssignRuleListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/rules/{rule_id}", response_model=AutoAssignRuleResponse)
async def get_rule(
    rule_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> AutoAssignRuleResponse:
    """Get a single auto-assignment rule by ID

    Requires 'assign' permission on 'reviews' (review_admin role or higher).
    """
    await _require_assign_permission(current_user, db)

    stmt = select(PullRequestReviewAutoAssignmentRule).where(
        PullRequestReviewAutoAssignmentRule.id == rule_id
    )
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NOT_FOUND",
                "message": f"Auto-assignment rule with ID {rule_id} not found",
            },
        )

    return AutoAssignRuleResponse.model_validate(rule)


@router.put("/rules/{rule_id}", response_model=AutoAssignRuleResponse)
async def update_rule(
    rule_id: int,
    rule_data: AutoAssignRuleUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> AutoAssignRuleResponse:
    """Update an auto-assignment rule

    Requires 'assign' permission on 'reviews' (review_admin role or higher).
    Only provided fields will be updated.
    """
    await _require_assign_permission(current_user, db)

    stmt = select(PullRequestReviewAutoAssignmentRule).where(
        PullRequestReviewAutoAssignmentRule.id == rule_id
    )
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NOT_FOUND",
                "message": f"Auto-assignment rule with ID {rule_id} not found",
            },
        )

    # Update only provided fields
    update_data = rule_data.model_dump(exclude_unset=True)
    if update_data:
        for field, value in update_data.items():
            setattr(rule, field, value)
        rule.updated_at = get_current_time()
        await db.flush()
        await db.refresh(rule)

        logger.info(
            "Auto-assign rule updated",
            extra={
                "rule_id": rule.id,
                "rule_name": rule.name,
                "updated_fields": list(update_data.keys()),
            },
        )

    return AutoAssignRuleResponse.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> None:
    """Delete an auto-assignment rule

    Requires 'assign' permission on 'reviews' (review_admin role or higher).
    """
    await _require_assign_permission(current_user, db)

    stmt = select(PullRequestReviewAutoAssignmentRule).where(
        PullRequestReviewAutoAssignmentRule.id == rule_id
    )
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NOT_FOUND",
                "message": f"Auto-assignment rule with ID {rule_id} not found",
            },
        )

    await db.delete(rule)
    await db.flush()

    logger.info(
        "Auto-assign rule deleted",
        extra={"rule_id": rule_id, "rule_name": rule.name},
    )


@router.patch("/rules/{rule_id}/toggle", response_model=AutoAssignRuleToggleResponse)
async def toggle_rule(
    rule_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> AutoAssignRuleToggleResponse:
    """Toggle the active status of an auto-assignment rule

    Flips is_active between true and false.
    Requires 'assign' permission on 'reviews' (review_admin role or higher).
    """
    await _require_assign_permission(current_user, db)

    stmt = select(PullRequestReviewAutoAssignmentRule).where(
        PullRequestReviewAutoAssignmentRule.id == rule_id
    )
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NOT_FOUND",
                "message": f"Auto-assignment rule with ID {rule_id} not found",
            },
        )

    rule.is_active = not rule.is_active
    rule.updated_at = get_current_time()
    await db.flush()
    await db.refresh(rule)

    status_text = "enabled" if rule.is_active else "disabled"
    logger.info(
        f"Auto-assign rule {status_text}",
        extra={
            "rule_id": rule.id,
            "rule_name": rule.name,
            "is_active": rule.is_active,
        },
    )

    return AutoAssignRuleToggleResponse(
        id=rule.id,
        name=rule.name,
        is_active=rule.is_active,
        message=f"Rule '{rule.name}' is now {status_text}.",
    )
