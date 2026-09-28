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
* ``GET/PUT/DELETE /release/diff/baseline`` - the baseline stored per repository
  that comparisons are narrowed against (writing it needs the manage permission).

All endpoints are backed by the Bitbucket Server REST API (or the GitHub
Enterprise equivalent) through the provider abstraction.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.exceptions import GitServiceException
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.models.release_check_baseline import ReleaseCheckBaseline
from src.schemas.release_diff import (
    ReleaseBaselineRequest,
    ReleaseBaselineResponse,
    ReleaseCommitCheckRequest,
    ReleaseCommitCheckResponse,
    ReleaseCompareRequest,
    ReleaseCompareResponse,
    ReleaseRefsRequest,
    ReleaseRefsResponse,
)
from src.services.rbac_service import RBACService
from src.services.release_check_baseline_service import ReleaseCheckBaselineService
from src.services.release_diff_service import ReleaseDiffService, resolve_provider_name
from src.utils.log import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/release/diff")

# Stored baselines are team configuration, so writing them is a management action.
RESOURCE_TYPE = "release_diff"


def get_release_diff_service() -> ReleaseDiffService:
    """Dependency provider for ReleaseDiffService."""
    return ReleaseDiffService()


def get_baseline_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReleaseCheckBaselineService:
    """Dependency provider for ReleaseCheckBaselineService."""
    return ReleaseCheckBaselineService(db)


def get_rbac_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RBACService:
    """Dependency provider for RBACService (release diff permissions)."""
    return RBACService(db)


async def ensure_manage_permission(rbac_service: RBACService, current_user: AuthUser) -> None:
    """Raise 403 unless the user may manage the release diff baseline."""
    allowed = await rbac_service.check_permission(
        auth_user_id=current_user.id,
        action="manage",
        resource_type=RESOURCE_TYPE,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "FORBIDDEN",
                "message": (
                    "Insufficient permissions to manage the release check baseline. "
                    "Review administrator role required."
                ),
            },
        )


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
        "line did since the fork point' means. When it is omitted, the baseline stored for "
        "the repository is used (disable that with `use_stored_baseline=false`).\n"
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
    service: Annotated[ReleaseDiffService, Depends(get_release_diff_service)],
    baseline_service: Annotated[ReleaseCheckBaselineService, Depends(get_baseline_service)],
) -> ReleaseCompareResponse:
    """Compare two releases and return the verdict plus the missing / added commits."""
    try:
        # the stored baseline narrows the comparison when the caller supplies none
        provider_name = resolve_provider_name(payload.git_provider)
        baseline_ref = await baseline_service.get_ref(
            git_provider=provider_name,
            project_key=payload.project_key,
            repository_slug=payload.repository_slug,
        )
        return await service.compare_releases(payload, baseline_ref=baseline_ref)
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
    service: Annotated[ReleaseDiffService, Depends(get_release_diff_service)],
) -> ReleaseRefsResponse:
    """List tags and branches for ref suggestions."""
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
    service: Annotated[ReleaseDiffService, Depends(get_release_diff_service)],
) -> ReleaseCommitCheckResponse:
    """Check whether the requested commits belong to the target release."""
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


def _baseline_response(
    *,
    project_key: str,
    repository_slug: str,
    git_provider: str,
    baseline: ReleaseCheckBaseline | None,
) -> ReleaseBaselineResponse:
    """Serialize a stored baseline, including the case where there is none."""
    if baseline is None:
        return ReleaseBaselineResponse(
            project_key=project_key.upper(),
            repository_slug=repository_slug,
            git_provider=git_provider,
            exists=False,
        )

    return ReleaseBaselineResponse(
        project_key=baseline.project_key,
        repository_slug=baseline.repository_slug,
        git_provider=baseline.git_provider,
        baseline_ref=baseline.baseline_ref,
        note=baseline.note,
        updated_by=baseline.updated_by,
        updated_date=baseline.updated_date.isoformat() if baseline.updated_date else None,
        exists=True,
    )


@router.get(
    "/baseline",
    response_model=ReleaseBaselineResponse,
    summary="Read the stored merge check baseline",
    description=(
        "Return the baseline stored for a repository, or `exists = false` when none is "
        "stored. The baseline is shared by everyone running the merge check."
    ),
)
async def get_release_baseline(
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    baseline_service: Annotated[ReleaseCheckBaselineService, Depends(get_baseline_service)],
    project_key: Annotated[str, Query(min_length=1, max_length=128)],
    repository_slug: Annotated[str, Query(min_length=1, max_length=256)],
    git_provider: Annotated[str | None, Query(max_length=32)] = None,
) -> ReleaseBaselineResponse:
    """Return the repository baseline; `exists = false` when there is none."""
    provider_name = resolve_provider_name(git_provider)
    baseline = await baseline_service.get(
        git_provider=provider_name,
        project_key=project_key,
        repository_slug=repository_slug,
    )
    return _baseline_response(
        project_key=project_key,
        repository_slug=repository_slug,
        git_provider=provider_name,
        baseline=baseline,
    )


@router.put(
    "/baseline",
    response_model=ReleaseBaselineResponse,
    summary="Store the merge check baseline",
    description=(
        "Store the baseline the merge check narrows against, for example the fork point of "
        "a maintenance line. Requires the manage permission on release diffing."
    ),
)
async def save_release_baseline(
    payload: ReleaseBaselineRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    baseline_service: Annotated[ReleaseCheckBaselineService, Depends(get_baseline_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> ReleaseBaselineResponse:
    """Store (or replace) the repository baseline."""
    await ensure_manage_permission(rbac_service, current_user)
    provider_name = resolve_provider_name(payload.git_provider)
    baseline = await baseline_service.save(
        git_provider=provider_name,
        project_key=payload.project_key,
        repository_slug=payload.repository_slug,
        baseline_ref=payload.baseline_ref,
        note=payload.note,
        updated_by=current_user.username,
    )
    return _baseline_response(
        project_key=payload.project_key,
        repository_slug=payload.repository_slug,
        git_provider=provider_name,
        baseline=baseline,
    )


@router.delete(
    "/baseline",
    response_model=ReleaseBaselineResponse,
    summary="Clear the merge check baseline",
    description="Remove the stored baseline of a repository. Requires the manage permission.",
)
async def clear_release_baseline(
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    baseline_service: Annotated[ReleaseCheckBaselineService, Depends(get_baseline_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
    project_key: Annotated[str, Query(min_length=1, max_length=128)],
    repository_slug: Annotated[str, Query(min_length=1, max_length=256)],
    git_provider: Annotated[str | None, Query(max_length=32)] = None,
) -> ReleaseBaselineResponse:
    """Clear the repository baseline."""
    await ensure_manage_permission(rbac_service, current_user)
    provider_name = resolve_provider_name(git_provider)
    await baseline_service.clear(
        git_provider=provider_name,
        project_key=project_key,
        repository_slug=repository_slug,
    )
    return _baseline_response(
        project_key=project_key,
        repository_slug=repository_slug,
        git_provider=provider_name,
        baseline=None,
    )
