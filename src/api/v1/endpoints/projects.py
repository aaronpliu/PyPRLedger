from datetime import datetime
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    ProjectListResponse,
    ProjectFilter,
    ProjectStats,
    ProjectDetailResponse,
)
from src.services.project_service import ProjectService
from src.core.exceptions import (
    ProjectNotFoundException,
    ResourceAlreadyExistsException,
)
from src.utils.metrics import MetricsCollector, OperationTimer, metrics

router = APIRouter()


# Get a project service instance with metrics
def get_project_service() -> ProjectService:
    """Get a project service instance"""
    return ProjectService(metrics_collector=metrics)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """
    Create a new project

    Args:
        project_data: The project data to create
        db: Database session
        project_service: Project service instance

    Returns:
        ProjectResponse: The created project

    Raises:
        ResourceAlreadyExistsException: If a project with the same ID or key already exists
    """
    try:
        project = await project_service.create_project(project_data, db)
        metrics.increment_project_count()
        return ProjectResponse(**project.dict())
    except ResourceAlreadyExistsException as e:
        metrics.increment_error(error_type=e.code, endpoint="POST /api/v1/projects")
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint="POST /api/v1/projects"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to create project"},
        )


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    project_key: Optional[str] = Query(None, description="Filter by project key"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    date_from: Optional[datetime] = Query(
        None, description="Filter projects created after this date"
    ),
    date_to: Optional[datetime] = Query(
        None, description="Filter projects created before this date"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
) -> ProjectListResponse:
    """
    List projects with filtering and pagination

    Args:
        project_id: Filter by project ID
        project_key: Filter by project key
        is_active: Filter by active status
        date_from: Filter projects created after this date
        date_to: Filter projects created before this date
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session
        project_service: Project service instance

    Returns:
        ProjectListResponse: List of projects with pagination info
    """
    try:
        filters = ProjectFilter(
            project_id=project_id,
            project_key=project_key,
            is_active=is_active,
            date_from=date_from,
            date_to=date_to,
        )

        projects, total = await project_service.list_projects(filters, page, page_size, db)

        return ProjectListResponse(
            items=[ProjectResponse(**p.to_dict()) for p in projects],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        metrics.increment_error(error_type="INTERNAL_SERVER_ERROR", endpoint="GET /api/v1/projects")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to list projects"},
        )


@router.get("/statistics", response_model=ProjectStats)
async def get_project_statistics(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    project_id: Optional[int] = Query(None, gt=0, description="Filter statistics by project ID"),
) -> ProjectStats:
    """
    Get project statistics

    Args:
        project_id: Optional project ID to filter statistics
        db: Database session
        project_service: Project service instance

    Returns:
        ProjectStats: Project statistics
    """
    try:
        stats = await project_service.get_project_statistics(project_id, db)

        # Update metrics
        metrics.set_projects_total(stats.total_projects)
        metrics.set_projects_active(stats.active_projects)

        return stats
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint="GET /api/v1/projects/statistics"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get project statistics",
            },
        )


@router.get("/active", response_model=ProjectListResponse)
async def get_active_projects(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of projects to return"),
) -> ProjectListResponse:
    """
    Get active projects

    Args:
        limit: Maximum number of projects to return
        db: Database session
        project_service: Project service instance

    Returns:
        ProjectListResponse: List of active projects
    """
    try:
        projects = await project_service.get_active_projects(db, limit)

        return ProjectListResponse(
            items=[ProjectResponse(**p.to_dict()) for p in projects],
            total=len(projects),
            page=1,
            page_size=limit,
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint="GET /api/v1/projects/active"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get active projects"},
        )


@router.get("/search", response_model=ProjectListResponse)
async def search_projects(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    search_term: str = Query(..., min_length=1, description="The search term"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
) -> ProjectListResponse:
    """
    Search projects by name, ID, or key

    Args:
        search_term: The search term
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session
        project_service: Project service instance

    Returns:
        ProjectListResponse: List of projects with pagination info
    """
    try:
        projects, total = await project_service.search_projects(search_term, page, page_size, db)

        return ProjectListResponse(
            items=[ProjectResponse(**p.to_dict()) for p in projects],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint="GET /api/v1/projects/search"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to search projects"},
        )


@router.get("/top/reviews", response_model=list)
async def get_projects_with_most_reviews(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    limit: int = Query(10, ge=1, le=100, description="Maximum number of projects to return"),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
) -> list:
    """
    Get projects with the most reviews in a given time period

    Args:
        limit: Maximum number of projects to return
        days: Number of days to look back
        db: Database session
        project_service: Project service instance

    Returns:
        list: List of projects with review counts
    """
    try:
        projects = await project_service.get_projects_with_most_reviews(db, limit, days)
        return projects
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint="GET /api/v1/projects/top/reviews"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get top projects by reviews",
            },
        )


@router.get("/top/reviewers", response_model=list)
async def get_projects_with_most_active_reviewers(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    limit: int = Query(10, ge=1, le=100, description="Maximum number of projects to return"),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
) -> list:
    """
    Get projects with the most active reviewers in a given time period

    Args:
        limit: Maximum number of projects to return
        days: Number of days to look back
        db: Database session
        project_service: Project service instance

    Returns:
        list: List of projects with active reviewer counts
    """
    try:
        projects = await project_service.get_projects_with_most_active_reviewers(db, limit, days)
        return projects
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint="GET /api/v1/projects/top/reviewers"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get top projects by reviewers",
            },
        )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectDetailResponse:
    """
    Get a project by ID with detailed information

    Args:
        project_id: The project database ID
        db: Database session
        project_service: Project service instance

    Returns:
        ProjectDetailResponse: The requested project with details

    Raises:
        ProjectNotFoundException: If the project doesn't exist
    """
    try:
        project = await project_service.get_project_by_id(project_id, db)
        if not project:
            metrics.increment_error(
                error_type="NOT_FOUND", endpoint=f"GET /api/v1/projects/{project_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"Project with ID {project_id} not found"},
            )

        # Get detailed project information
        project_dict = await project_service.get_project_with_stats(project_id, db)

        return ProjectDetailResponse(**project_dict)
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"GET /api/v1/projects/{project_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get project"},
        )


@router.get("/id/{project_id}", response_model=ProjectResponse)
async def get_project_by_project_id(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """
    Get a project by project identifier

    Args:
        project_id: The project identifier
        db: Database session
        project_service: Project service instance

    Returns:
        ProjectResponse: The requested project

    Raises:
        ProjectNotFoundException: If the project doesn't exist
    """
    try:
        project = await project_service.get_project_by_project_id(project_id, db)
        if not project:
            metrics.increment_error(
                error_type="NOT_FOUND", endpoint=f"GET /api/v1/projects/id/{project_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"Project with ID {project_id} not found"},
            )
        return ProjectResponse(**project.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"GET /api/v1/projects/id/{project_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get project by ID"},
        )


@router.get("/key/{project_key}", response_model=ProjectResponse)
async def get_project_by_key(
    project_key: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """
    Get a project by project key

    Args:
        project_key: The project key
        db: Database session
        project_service: Project service instance

    Returns:
        ProjectResponse: The requested project

    Raises:
        ProjectNotFoundException: If the project doesn't exist
    """
    try:
        project = await project_service.get_project_by_key(project_key, db)
        if not project:
            metrics.increment_error(
                error_type="NOT_FOUND", endpoint=f"GET /api/v1/projects/key/{project_key}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Project with key {project_key} not found",
                },
            )
        return ProjectResponse(**project.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"GET /api/v1/projects/key/{project_key}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get project by key"},
        )


@router.get("/name/{project_name}", response_model=ProjectResponse)
async def get_project_by_name(
    project_name: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """
    Get a project by name (partial match)

    Args:
        project_name: The project name to search for
        db: Database session
        project_service: Project service instance

    Returns:
        ProjectResponse: The requested project

    Raises:
        ProjectNotFoundException: If the project doesn't exist
    """
    try:
        project = await project_service.get_project_by_name(project_name, db)
        if not project:
            metrics.increment_error(
                error_type="NOT_FOUND", endpoint=f"GET /api/v1/projects/name/{project_name}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Project with name '{project_name}' not found",
                },
            )
        return ProjectResponse(**project.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"GET /api/v1/projects/name/{project_name}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get project by name"},
        )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_update: ProjectUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """
    Update a project

    Args:
        project_id: The project database ID
        project_update: The update data
        db: Database session
        project_service: Project service instance

    Returns:
        ProjectResponse: The updated project

    Raises:
        ProjectNotFoundException: If the project doesn't exist
    """
    try:
        project = await project_service.update_project(project_id, project_update, db)
        return ProjectResponse(**project.to_dict())
    except ProjectNotFoundException as e:
        metrics.increment_error(error_type=e.code, endpoint=f"PUT /api/v1/projects/{project_id}")
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"PUT /api/v1/projects/{project_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to update project"},
        )


@router.patch("/{project_id}/activate", response_model=ProjectResponse)
async def activate_project(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """
    Activate a project

    Args:
        project_id: The project database ID
        db: Database session
        project_service: Project service instance

    Returns:
        ProjectResponse: The updated project

    Raises:
        ProjectNotFoundException: If the project doesn't exist
    """
    try:
        project = await project_service.activate_project(project_id, db)
        return ProjectResponse(**project.to_dict())
    except ProjectNotFoundException as e:
        metrics.increment_error(
            error_type=e.code, endpoint=f"PATCH /api/v1/projects/{project_id}/activate"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"PATCH /api/v1/projects/{project_id}/activate",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to activate project"},
        )


@router.patch("/{project_id}/deactivate", response_model=ProjectResponse)
async def deactivate_project(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """
    Deactivate a project

    Args:
        project_id: The project database ID
        db: Database session
        project_service: Project service instance

    Returns:
        ProjectResponse: The updated project

    Raises:
        ProjectNotFoundException: If the project doesn't exist
    """
    try:
        project = await project_service.deactivate_project(project_id, db)
        return ProjectResponse(**project.to_dict())
    except ProjectNotFoundException as e:
        metrics.increment_error(
            error_type=e.code, endpoint=f"PATCH /api/v1/projects/{project_id}/deactivate"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"PATCH /api/v1/projects/{project_id}/deactivate",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to deactivate project"},
        )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> None:
    """
    Delete a project

    Args:
        project_id: The project database ID
        db: Database session
        project_service: Project service instance

    Returns:
        None: Successful deletion returns 204 No Content

    Raises:
        ProjectNotFoundException: If the project doesn't exist
    """
    try:
        deleted = await project_service.delete_project(project_id, db)
        if not deleted:
            metrics.increment_error(
                error_type="NOT_FOUND", endpoint=f"DELETE /api/v1/projects/{project_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"Project with ID {project_id} not found"},
            )
        metrics.decrement_project_count()
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"DELETE /api/v1/projects/{project_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to delete project"},
        )


@router.get("/{project_id}/repositories/count", response_model=dict)
async def get_project_repository_count(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> dict:
    """
    Get the number of repositories in a project

    Args:
        project_id: The project database ID
        db: Database session
        project_service: Project service instance

    Returns:
        dict: Dictionary containing the repository count

    Raises:
        ProjectNotFoundException: If the project doesn't exist
    """
    try:
        count = await project_service.get_project_repository_count(project_id, db)
        return {"project_id": project_id, "repository_count": count}
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"GET /api/v1/projects/{project_id}/repositories/count",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get repository count"},
        )


@router.get("/{project_id}/reviews/count", response_model=dict)
async def get_project_review_count(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> dict:
    """
    Get the number of reviews in a project

    Args:
        project_id: The project database ID
        db: Database session
        project_service: Project service instance

    Returns:
        dict: Dictionary containing the review count

    Raises:
        ProjectNotFoundException: If the project doesn't exist
    """
    try:
        count = await project_service.get_project_review_count(project_id, db)
        return {"project_id": project_id, "review_count": count}
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"GET /api/v1/projects/{project_id}/reviews/count",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get review count"},
        )


@router.get("/{project_id}/reviewers/count", response_model=dict)
async def get_project_active_reviewer_count(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> dict:
    """
    Get the number of active reviewers in a project

    Args:
        project_id: The project database ID
        db: Database session
        project_service: Project service instance

    Returns:
        dict: Dictionary containing the active reviewer count

    Raises:
        ProjectNotFoundException: If the project doesn't exist
    """
    try:
        count = await project_service.get_project_active_reviewer_count(project_id, db)
        return {"project_id": project_id, "active_reviewer_count": count}
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"GET /api/v1/projects/{project_id}/reviewers/count",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get active reviewer count",
            },
        )
