from datetime import datetime
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.schemas.user import (
    UserCreate,
    UserResponse,
    UserUpdate,
    UserListResponse,
    UserStats,
    UserLogin,
)
from src.services.user_service import UserService
from src.core.exceptions import (
    UserNotFoundException,
    UserAlreadyExistsException,
    InvalidCredentialsException,
)
from src.utils.metrics import MetricsCollector, OperationTimer, metrics

router = APIRouter()

# Get a user service instance with metrics
def get_user_service() -> UserService:
    """Get a user service instance"""
    return UserService(metrics_collector=metrics)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)]
) -> UserResponse:
    """
    Create a new user
    
    Args:
        user_data: The user data to create
        db: Database session
        user_service: User service instance
        
    Returns:
        UserResponse: The created user
        
    Raises:
        UserAlreadyExistsException: If a user with the same username or email already exists
    """
    try:
        user = await user_service.create_user(user_data, db)
        metrics.increment_user_count()
        return UserResponse(**user.dict())
    except UserAlreadyExistsException as e:
        metrics.increment_error(
            error_type=e.code,
            endpoint="POST /api/v1/users"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": e.code,
                "message": e.message,
                "detail": e.detail
            }
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint="POST /api/v1/users"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to create user"
            }
        )


@router.get("", response_model=UserListResponse)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    active: Optional[bool] = Query(None, description="Filter by active status"),
    is_reviewer: Optional[bool] = Query(None, description="Filter by reviewer status"),
    username: Optional[str] = Query(None, description="Filter by username (partial match)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page")
) -> UserListResponse:
    """
    List users with filtering and pagination
    
    Args:
        active: Filter by active status
        is_reviewer: Filter by reviewer status
        username: Filter by username (partial match)
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session
        user_service: User service instance
        
    Returns:
        UserListResponse: List of users with pagination info
    """
    try:
        users, total = await user_service.list_users(
            active=active,
            is_reviewer=is_reviewer,
            username=username,
            page=page,
            page_size=page_size,
            db=db
        )
        
        return UserListResponse(
            items=[UserResponse(**u.to_dict()) for u in users],
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint="GET /api/v1/users"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to list users"
            }
        )


@router.get("/statistics", response_model=UserStats)
async def get_user_statistics(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)]
) -> UserStats:
    """
    Get user statistics
    
    Args:
        db: Database session
        user_service: User service instance
        
    Returns:
        UserStats: User statistics
    """
    try:
        stats = await user_service.get_user_statistics(db)
        
        # Update metrics
        metrics.set_users_total(stats.total_users)
        metrics.set_users_active(stats.active_users)
        metrics.set_reviewers_total(stats.total_reviewers)
        metrics.set_reviewers_active(stats.active_reviewers)
        
        return stats
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint="GET /api/v1/users/statistics"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get user statistics"
            }
        )


@router.get("/active", response_model=UserListResponse)
async def get_active_users(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of users to return")
) -> UserListResponse:
    """
    Get active users
    
    Args:
        limit: Maximum number of users to return
        db: Database session
        user_service: User service instance
        
    Returns:
        UserListResponse: List of active users
    """
    try:
        active_users = await user_service.get_active_users(db, limit)
        
        return UserListResponse(
            items=[UserResponse(**u.to_dict()) for u in active_users],
            total=len(active_users),
            page=1,
            page_size=limit
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint="GET /api/v1/users/active"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get active users"
            }
        )


@router.get("/reviewers", response_model=UserListResponse)
async def get_reviewers(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of reviewers to return")
) -> UserListResponse:
    """
    Get active reviewers
    
    Args:
        limit: Maximum number of reviewers to return
        db: Database session
        user_service: User service instance
        
    Returns:
        UserListResponse: List of active reviewers
    """
    try:
        reviewers = await user_service.get_active_reviewers(db, limit)
        
        return UserListResponse(
            items=[UserResponse(**r.to_dict()) for r in reviewers],
            total=len(reviewers),
            page=1,
            page_size=limit
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint="GET /api/v1/users/reviewers"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get reviewers"
            }
        )


@router.post("/login", response_model=dict)
async def login(
    credentials: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)]
) -> dict:
    """
    Authenticate a user
    
    Args:
        credentials: User login credentials
        db: Database session
        user_service: User service instance
        
    Returns:
        dict: Authentication result with user info and token
        
    Raises:
        InvalidCredentialsException: If credentials are invalid
    """
    try:
        user = await user_service.validate_credentials(
            username=credentials.username,
            password=credentials.password,
            db=db
        )
        
        return {
            "success": True,
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "is_reviewer": user.is_reviewer
        }
    except InvalidCredentialsException as e:
        metrics.increment_error(
            error_type=e.code,
            endpoint="POST /api/v1/users/login"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": e.code,
                "message": e.message
            }
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint="POST /api/v1/users/login"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to authenticate user"
            }
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)]
) -> UserResponse:
    """
    Get a user by ID
    
    Args:
        user_id: The user ID
        db: Database session
        user_service: User service instance
        
    Returns:
        UserResponse: The requested user
        
    Raises:
        UserNotFoundException: If the user doesn't exist
    """
    try:
        user = await user_service.get_user_by_id(user_id, db)
        if not user:
            metrics.increment_error(
                error_type="NOT_FOUND",
                endpoint=f"GET /api/v1/users/{user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"User with ID {user_id} not found"
                }
            )
        return UserResponse(**user.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"GET /api/v1/users/{user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get user"
            }
        )


@router.get("/username/{username}", response_model=UserResponse)
async def get_user_by_username(
    username: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)]
) -> UserResponse:
    """
    Get a user by username
    
    Args:
        username: The username
        db: Database session
        user_service: User service instance
        
    Returns:
        UserResponse: The requested user
        
    Raises:
        UserNotFoundException: If the user doesn't exist
    """
    try:
        user = await user_service.get_user_by_username(username, db)
        if not user:
            metrics.increment_error(
                error_type="NOT_FOUND",
                endpoint=f"GET /api/v1/users/username/{username}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"User with username '{username}' not found"
                }
            )
        return UserResponse(**user.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"GET /api/v1/users/username/{username}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get user by username"
            }
        )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)]
) -> UserResponse:
    """
    Update a user
    
    Args:
        user_id: The user ID
        user_update: The update data
        db: Database session
        user_service: User service instance
        
    Returns:
        UserResponse: The updated user
        
    Raises:
        UserNotFoundException: If the user doesn't exist
    """
    try:
        user = await user_service.update_user(user_id, user_update, db)
        return UserResponse(**user.to_dict())
    except UserNotFoundException as e:
        metrics.increment_error(
            error_type=e.code,
            endpoint=f"PUT /api/v1/users/{user_id}"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": e.code,
                "message": e.message,
                "detail": e.detail
            }
        )
    except UserAlreadyExistsException as e:
        metrics.increment_error(
            error_type=e.code,
            endpoint=f"PUT /api/v1/users/{user_id}"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": e.code,
                "message": e.message,
                "detail": e.detail
            }
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"PUT /api/v1/users/{user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to update user"
            }
        )


@router.patch("/{user_id}/toggle-reviewer", response_model=UserResponse)
async def toggle_reviewer_status(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)]
) -> UserResponse:
    """
    Toggle reviewer status for a user
    
    Args:
        user_id: The user ID
        db: Database session
        user_service: User service instance
        
    Returns:
        UserResponse: The updated user
        
    Raises:
        UserNotFoundException: If the user doesn't exist
    """
    try:
        user = await user_service.toggle_reviewer_status(user_id, db)
        return UserResponse(**user.to_dict())
    except UserNotFoundException as e:
        metrics.increment_error(
            error_type=e.code,
            endpoint=f"PATCH /api/v1/users/{user_id}/toggle-reviewer"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": e.code,
                "message": e.message,
                "detail": e.detail
            }
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"PATCH /api/v1/users/{user_id}/toggle-reviewer"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to toggle reviewer status"
            }
        )


@router.patch("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)]
) -> UserResponse:
    """
    Activate a user
    
    Args:
        user_id: The user ID
        db: Database session
        user_service: User service instance
        
    Returns:
        UserResponse: The updated user
        
    Raises:
        UserNotFoundException: If the user doesn't exist
    """
    try:
        user = await user_service.activate_user(user_id, db)
        return UserResponse(**user.to_dict())
    except UserNotFoundException as e:
        metrics.increment_error(
            error_type=e.code,
            endpoint=f"PATCH /api/v1/users/{user_id}/activate"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": e.code,
                "message": e.message,
                "detail": e.detail
            }
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"PATCH /api/v1/users/{user_id}/activate"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to activate user"
            }
        )


@router.patch("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)]
) -> UserResponse:
    """
    Deactivate a user
    
    Args:
        user_id: The user ID
        db: Database session
        user_service: User service instance
        
    Returns:
        UserResponse: The updated user
        
    Raises:
        UserNotFoundException: If the user doesn't exist
    """
    try:
        user = await user_service.deactivate_user(user_id, db)
        return UserResponse(**user.to_dict())
    except UserNotFoundException as e:
        metrics.increment_error(
            error_type=e.code,
            endpoint=f"PATCH /api/v1/users/{user_id}/deactivate"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": e.code,
                "message": e.message,
                "detail": e.detail
            }
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"PATCH /api/v1/users/{user_id}/deactivate"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to deactivate user"
            }
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)]
) -> None:
    """
    Delete a user
    
    Args:
        user_id: The user ID
        db: Database session
        user_service: User service instance
        
    Returns:
        None: Successful deletion returns 204 No Content
        
    Raises:
        UserNotFoundException: If the user doesn't exist
    """
    try:
        deleted = await user_service.delete_user(user_id, db)
        if not deleted:
            metrics.increment_error(
                error_type="NOT_FOUND",
                endpoint=f"DELETE /api/v1/users/{user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"User with ID {user_id} not found"
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"DELETE /api/v1/users/{user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to delete user"
            }
        )