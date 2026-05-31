"""Global search endpoint for searching across multiple resource types."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.exceptions import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.models.project import Project
from src.models.project_registry import ProjectRegistry
from src.models.pull_request import PullRequestReviewBase
from src.models.user import User
from src.utils.metrics import metrics


logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])

# Maximum execution time per search query in seconds.
# Queries exceeding this timeout are interrupted at the MySQL level,
# which safely releases the database connection back to the pool.
SEARCH_QUERY_TIMEOUT = 5


@router.get("/")
async def global_search(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    type: str | None = Query(None, description="Filter by type: review, user, project"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results per type"),
) -> dict:
    """
    Global search across reviews, users, and projects.

    Each search type executes sequentially on the shared session connection.
    Individual search failures are handled gracefully and return empty results.
    """
    try:
        results: dict[str, list] = {
            "reviews": [],
            "users": [],
            "projects": [],
        }

        if not type or type == "review":
            results["reviews"] = await _search_reviews(db, q, limit)

        if not type or type == "user":
            results["users"] = await _search_users(db, q, limit)

        if not type or type == "project":
            results["projects"] = await _search_projects(db, q, limit)

        return results

    except Exception as e:
        logger.error(f"Global search failed: {e}", exc_info=True)
        metrics.increment_error(error_type="SEARCH_ERROR", endpoint="GET /api/v1/search/")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "SEARCH_FAILED", "message": "Search operation failed"},
        )


async def _search_reviews(db: AsyncSession, query: str, limit: int) -> list[dict]:
    """Search pull request reviews by PR ID, project key, or repository slug."""
    try:
        stmt = (
            select(PullRequestReviewBase)
            .where(
                PullRequestReviewBase.pull_request_id.ilike(f"%{query}%")
                | PullRequestReviewBase.project_key.ilike(f"%{query}%")
                | PullRequestReviewBase.repository_slug.ilike(f"%{query}%")
            )
            .order_by(PullRequestReviewBase.created_date.desc())
            .limit(limit)
            .execution_options(max_execution_time=SEARCH_QUERY_TIMEOUT)
        )

        result = await db.execute(stmt)
        reviews = result.scalars().all()

        return [
            {
                "id": review.id,
                "type": "review",
                "title": f"PR #{review.pull_request_id}",
                "description": f"{review.project_key}/{review.repository_slug}",
                "url": f"/reviews/{review.id}",
                "created_at": review.created_date.isoformat() if review.created_date else "",
            }
            for review in reviews
        ]
    except Exception as e:
        logger.warning(f"Review search failed (query={query!r}): {e}")
        return []


async def _search_users(db: AsyncSession, query: str, limit: int) -> list[dict]:
    """Search users by username or display name."""
    try:
        stmt = (
            select(User)
            .where(User.username.ilike(f"%{query}%") | User.display_name.ilike(f"%{query}%"))
            .limit(limit)
            .execution_options(max_execution_time=SEARCH_QUERY_TIMEOUT)
        )

        result = await db.execute(stmt)
        users = result.scalars().all()

        return [
            {
                "id": user.id,
                "type": "user",
                "title": user.display_name or user.username,
                "description": f"@{user.username}",
                "url": "/admin/users",
                "created_at": "",
            }
            for user in users
        ]
    except Exception as e:
        logger.warning(f"User search failed (query={query!r}): {e}")
        return []


async def _search_projects(db: AsyncSession, query: str, limit: int) -> list[dict]:
    """Search projects by name, key, or app name."""
    try:
        stmt = (
            select(ProjectRegistry)
            .join(Project, ProjectRegistry.project_key == Project.project_key)
            .where(
                ProjectRegistry.app_name.ilike(f"%{query}%")
                | ProjectRegistry.project_key.ilike(f"%{query}%")
                | Project.project_name.ilike(f"%{query}%")
            )
            .limit(limit)
            .execution_options(max_execution_time=SEARCH_QUERY_TIMEOUT)
        )

        result = await db.execute(stmt)
        projects = result.scalars().all()

        return [
            {
                "id": project.id,
                "type": "project",
                "title": project.project.project_name or project.app_name,
                "description": f"{project.project_key} - {project.app_name}",
                "url": f"/reviews?project={project.project_key}",
                "created_at": "",
            }
            for project in projects
        ]
    except Exception as e:
        logger.warning(f"Project search failed (query={query!r}): {e}")
        return []
