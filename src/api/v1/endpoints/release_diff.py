"""Release diff endpoints.

Operations over the git provider compare API:

* ``POST /release/diff/compare`` - the single comparison: is everything from the
  source release contained in the target release (the verdict), and what does the
  target add on top of it? Answered by provider differences, so the verdict is
  definitive or explicitly inconclusive.
* ``POST /release/diff/check``   - check whether one or more commits belong to
  a target release (each commit answered by the provider).
* ``POST /release/diff/refs``    - list tags / branches of a repository so the UI
  can suggest release refs (arbitrary refs can still be typed manually).

The baseline a comparison is narrowed against is optional and belongs to that
comparison alone: it narrows two releases of one line, and a repository holds
several lines.

All endpoints are backed by the Bitbucket Server REST API (or the GitHub
Enterprise equivalent) through the provider abstraction.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.exceptions import GitServiceException
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.schemas.release_diff import (
    ReleaseCommitCheckRequest,
    ReleaseCommitCheckResponse,
    ReleaseCompareRequest,
    ReleaseCompareResponse,
    ReleaseRefsRequest,
    ReleaseRefsResponse,
)
from src.services.git_provider_resolver import with_repository_provider
from src.services.release_diff_service import ReleaseDiffService
from src.utils.log import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/release/diff")


def get_release_diff_service() -> ReleaseDiffService:
    """Dependency provider for ReleaseDiffService."""
    return ReleaseDiffService()


@router.post(
    "/compare",
    response_model=ReleaseCompareResponse,
    summary="Compare two release versions",
    description=(
        "One comparison answers both halves of the question:\n\n"
        "* `verdict` - is every commit of `source_ref` contained in `target_ref`? It is "
        "derived from the provider difference `source_ref \\ target_ref`, so it is "
        "definitive (`contained` / `missing`) or explicitly `inconclusive` - never a pass "
        "derived from a truncated listing.\n"
        "* `missing_commits` / `added_commits` - what the target lacks and what it adds.\n\n"
        "`baseline_ref` is optional and narrows **both** directions: difference commits "
        "that already existed at the baseline are ignored, which is what 'the work this "
        "line did since the fork point' means. It belongs to this comparison alone, since "
        "a repository holds several release lines with a fork point each.\n"
        "```json\n"
        "{\n"
        '  "source_ref": "v1.1.5", "target_ref": "v2.3.0", "baseline_ref": "v1.0.0"\n'
        "}\n"
        "```"
    ),
)
async def compare_releases(
    payload: ReleaseCompareRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReleaseDiffService, Depends(get_release_diff_service)],
) -> ReleaseCompareResponse:
    """Compare two releases and return the verdict plus the missing / added commits."""
    payload = await with_repository_provider(payload, db)
    try:
        return await service.compare_releases(payload)
    except GitServiceException as e:
        logger.error(
            "Git provider failed while comparing releases",
            extra={
                "project_key": payload.project_key,
                "repository_slug": payload.repository_slug,
                "user_id": current_user.id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "git_service_error",
                "message": str(e.detail) if isinstance(e.detail, dict) else str(e),
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bad_request", "message": str(e)},
        )


@router.post(
    "/refs",
    response_model=ReleaseRefsResponse,
    summary="List tags and branches of a repository",
    description=(
        "Return the tag and branch names of a repository so the UI can suggest release "
        "refs. The list is only a suggestion - any ref (tag, branch or commit sha) can "
        "still be used for compare / check requests."
    ),
)
async def list_release_refs(
    payload: ReleaseRefsRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReleaseDiffService, Depends(get_release_diff_service)],
) -> ReleaseRefsResponse:
    """List tags and branches for ref suggestions."""
    payload = await with_repository_provider(payload, db)
    try:
        return await service.list_refs(payload)
    except GitServiceException as e:
        logger.error(
            "Git provider failed while listing release refs",
            extra={
                "project_key": payload.project_key,
                "repository_slug": payload.repository_slug,
                "user_id": current_user.id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "git_service_error",
                "message": str(e.detail) if isinstance(e.detail, dict) else str(e),
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bad_request", "message": str(e)},
        )


@router.post(
    "/check",
    response_model=ReleaseCommitCheckResponse,
    summary="Check commits against a target release",
    description=(
        "Verify whether one or more commits (full or short SHA) are part of a target "
        "release. Optionally scope the release to the commits between "
        "`target_release_base_ref` and `target_release_ref`."
    ),
)
async def check_release_commits(
    payload: ReleaseCommitCheckRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReleaseDiffService, Depends(get_release_diff_service)],
) -> ReleaseCommitCheckResponse:
    """Check whether the requested commits belong to the target release."""
    payload = await with_repository_provider(payload, db)
    try:
        return await service.check_commits(payload)
    except GitServiceException as e:
        logger.error(
            "Git provider failed while checking release commits",
            extra={
                "project_key": payload.project_key,
                "repository_slug": payload.repository_slug,
                "user_id": current_user.id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "git_service_error",
                "message": str(e.detail) if isinstance(e.detail, dict) else str(e),
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bad_request", "message": str(e)},
        )
