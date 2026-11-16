"""Repository insights endpoint.

One reading feeds a whole dashboard page: KPIs, trends, distributions and the
last few reviews, scoped to a repository or to every repository of a project and
limited to what the caller may see.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.exceptions import ForbiddenException
from src.core.permissions import CurrentRepositoryAccess
from src.schemas.insights import RepositoryInsights
from src.services.insights_service import InsightsService


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/repository",
    response_model=RepositoryInsights,
    summary="Read one repository (or project) into a dashboard payload",
    description=(
        "Aggregate the PR reviews, scores, assignments and recent activity of a "
        "repository, or of every repository of a project when `repository_slug` "
        "is omitted. Only repositories the caller holds a grant for are read; an "
        "empty grant set answers with an empty reading rather than an unrestricted "
        "one. The answer is cached for a minute, so a polling page stays cheap."
    ),
)
async def get_repository_insights(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    access: CurrentRepositoryAccess,
    project_key: Annotated[
        str | None,
        Query(min_length=1, max_length=32, description="Project to read"),
    ] = None,
    repository_slug: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=128,
            description="Repository to read; omit to read the project's repositories",
        ),
    ] = None,
    days: Annotated[int, Query(ge=1, le=365, description="How far back to look")] = 30,
    period: Annotated[
        str, Query(pattern="^(daily|weekly|monthly)$", description="Trend bucket")
    ] = "weekly",
) -> RepositoryInsights:
    """Read the scope into KPIs, trends, distributions and recent reviews."""
    try:
        service = InsightsService(allowed_pairs=access)
        return await service.get_repository_insights(
            db,
            project_key=project_key,
            repository_slug=repository_slug,
            days=days,
            period=period,
        )
    except ForbiddenException as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message, "detail": exc.detail},
        ) from exc
    except Exception as exc:
        logger.error("Failed to read repository insights: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to read insights"},
        ) from exc
