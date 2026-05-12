from typing import Any

from fastapi import status
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorCode:
    """Error code constants"""

    # General errors (1000-1999)
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"

    # Request-related errors (2000-2999)
    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"

    # Authentication and authorization errors (3000-3999)
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"

    # Resource-related errors (4000-4999)
    NOT_FOUND = "NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    RESOURCE_LOCKED = "RESOURCE_LOCKED"

    # Business logic errors (5000-5999)
    INVALID_OPERATION = "INVALID_OPERATION"
    INVALID_STATUS = "INVALID_STATUS"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"

    # Database errors (6000-6999)
    DATABASE_ERROR = "DATABASE_ERROR"
    DATABASE_CONNECTION_ERROR = "DATABASE_CONNECTION_ERROR"
    DATABASE_TIMEOUT = "DATABASE_TIMEOUT"

    # Cache errors (7000-7999)
    CACHE_ERROR = "CACHE_ERROR"
    CACHE_CONNECTION_ERROR = "CACHE_CONNECTION_ERROR"
    CACHE_MISS = "CACHE_MISS"

    # External service errors (8000-8999)
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    GIT_SERVICE_ERROR = "GIT_SERVICE_ERROR"

    # Rate limiting errors (9000-9999)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


class AppException(StarletteHTTPException):
    """Base application exception class

    All custom exceptions should inherit from this class.
    Simplified interface - subclasses define their own detail structure.
    Supports i18n through message_key and message_params.
    """

    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: Any = None,
        headers: dict[str, str] | None = None,
        message_key: str | None = None,
        message_params: dict[str, Any] | None = None,
    ):
        self.message_key = message_key
        self.message_params = message_params or {}
        super().__init__(status_code=status_code, detail=detail, headers=headers)

    def get_message(self, lang: str = "en") -> str:
        """Get translated message based on language"""
        if self.message_key:
            from src.utils.i18n import i18n

            return i18n.t(self.message_key, lang, **self.message_params)

        # Fallback to message from detail if no message_key
        if isinstance(self.detail, dict) and "message" in self.detail:
            return self.detail["message"]

        return str(self.detail) if self.detail else "An error occurred"


class BadRequestException(AppException):
    """400 Bad Request"""

    def __init__(
        self,
        message: str = "Bad request",
        message_key: str | None = None,
        message_params: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bad_request", "message": message},
            message_key=message_key or "errors.bad_request",
            message_params=message_params,
        )


class ValidationException(AppException):
    """422 Validation Error"""

    def __init__(
        self,
        message: str = "Validation failed",
        message_key: str | None = None,
        message_params: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation_error", "message": message},
            message_key=message_key or "errors.validation_failed",
            message_params=message_params,
        )


class UnauthorizedException(AppException):
    """401 Unauthorized"""

    def __init__(
        self,
        message: str = "Unauthorized",
        message_key: str | None = None,
        message_params: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": message},
            message_key=message_key or "errors.unauthorized",
            message_params=message_params,
        )


class ForbiddenException(AppException):
    """403 Forbidden"""

    def __init__(
        self,
        message: str = "Access forbidden",
        message_key: str | None = None,
        message_params: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": message},
            message_key=message_key or "errors.access_forbidden",
            message_params=message_params,
        )


class NotFoundException(AppException):
    """404 Not Found"""

    def __init__(
        self,
        message: str = "Resource not found",
        message_key: str | None = None,
        message_params: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": message},
            message_key=message_key or "errors.resource_not_found",
            message_params=message_params,
        )


class ResourceAlreadyExistsException(AppException):
    """409 Conflict - Resource Already Exists"""

    def __init__(
        self,
        message: str = "Resource already exists",
        message_key: str | None = None,
        message_params: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "resource_already_exists", "message": message},
            message_key=message_key or "errors.resource_already_exists",
            message_params=message_params,
        )


class InternalServerException(AppException):
    """500 Internal Server Error"""

    def __init__(self, message: str = "Internal server error"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_server_error", "message": message},
            message_key="errors.internal_server_error",
        )


class DatabaseException(AppException):
    """Database related errors"""

    def __init__(self, message: str = "Database error"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "database_error", "message": message},
            message_key="errors.database_error",
        )


class DatabaseConnectionException(AppException):
    """Database connection error"""

    def __init__(self, message: str = "Database connection error"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "database_connection_error", "message": message},
            message_key="errors.database_connection_error",
        )


class CacheException(AppException):
    """Cache related errors"""

    def __init__(self, message: str = "Cache error"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "cache_error", "message": message},
            message_key="errors.cache_error",
        )


class RateLimitException(AppException):
    """Rate limit exceeded"""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "rate_limit_exceeded", "message": message},
            message_key="errors.rate_limit_exceeded",
        )


class ReviewNotFoundException(NotFoundException):
    """Review not found"""

    def __init__(self, pull_request_id: str):
        super().__init__(
            message=f"Review with ID {pull_request_id} not found",
            message_key="errors.review_not_found",
            message_params={"pull_request_id": pull_request_id},
        )


class ReviewAlreadyExistsException(ResourceAlreadyExistsException):
    """Review already exists"""

    def __init__(self, pull_request_id: str):
        super().__init__(
            message=f"Review with ID {pull_request_id} already exists",
            message_key="errors.review_already_exists",
            message_params={"pull_request_id": pull_request_id},
        )


class InvalidReviewDataException(BadRequestException):
    """Invalid review data"""

    def __init__(self, message: str = "Invalid review data"):
        super().__init__(
            message=message,
            message_key="errors.invalid_review_data",
        )


class ReviewStatusException(BadRequestException):
    """Invalid review status"""

    def __init__(self, current_status: str, target_status: str, message: str | None = None):
        message = message or f"Cannot transition review from {current_status} to {target_status}"
        super().__init__(
            message=message,
            message_key="errors.status_transition_not_allowed",
            message_params={"current_status": current_status, "target_status": target_status},
        )


class UserNotFoundException(NotFoundException):
    """User not found"""

    def __init__(self, user_id: int | None = None, username: str | None = None):
        if user_id:
            message = f"User with ID {user_id} not found"
            message_key = "errors.user_not_found_by_id"
            message_params = {"user_id": user_id}
        elif username:
            message = f"User with username '{username}' not found"
            message_key = "errors.user_not_found_by_username"
            message_params = {"username": username}
        else:
            message = "User not found"
            message_key = "errors.user_not_found"
            message_params = {}
        super().__init__(message=message, message_key=message_key, message_params=message_params)


class UserAlreadyExistsException(ResourceAlreadyExistsException):
    """User already exists"""

    def __init__(self, username: str | None = None, email: str | None = None):
        if username:
            message = f"Username '{username}' already exists"
            message_key = "errors.user_already_exists_by_username"
            message_params = {"username": username}
        elif email:
            message = f"Email '{email}' already registered"
            message_key = "errors.user_already_exists_by_email"
            message_params = {"email": email}
        else:
            message = "User already exists"
            message_key = "errors.user_already_exists"
            message_params = {}
        super().__init__(message=message, message_key=message_key, message_params=message_params)


class InvalidCredentialsException(UnauthorizedException):
    """Invalid login credentials"""

    def __init__(self):
        super().__init__(
            message="Invalid username or password",
            message_key="errors.invalid_credentials",
        )


class UserInactiveException(UnauthorizedException):
    """User account is inactive"""

    def __init__(self, username: str):
        super().__init__(
            message=f"User account '{username}' is inactive",
            message_key="errors.unauthorized",
            message_params={"username": username},
        )


class ProjectNotFoundException(NotFoundException):
    """Project not found"""

    def __init__(self, project_id: int | None = None, project_key: str | None = None):
        if project_id:
            message = f"Project with ID {project_id} not found"
            message_key = "errors.project_not_found_by_id"
            message_params = {"project_id": project_id}
        elif project_key:
            message = f"Project with key '{project_key}' not found"
            message_key = "errors.project_not_found_by_key"
            message_params = {"project_key": project_key}
        else:
            message = "Project not found"
            message_key = "errors.project_not_found"
            message_params = {}
        super().__init__(message=message, message_key=message_key, message_params=message_params)


class RepositoryNotFoundException(NotFoundException):
    """Repository not found"""

    def __init__(self, repository_id: str | None = None, repository_slug: str | None = None):
        if repository_id:
            message = f"Repository with ID {repository_id} not found"
            message_key = "errors.repository_not_found_by_id"
            message_params = {"repository_id": repository_id}
        elif repository_slug:
            message = f"Repository with slug '{repository_slug}' not found"
            message_key = "errors.repository_not_found_by_slug"
            message_params = {"repository_slug": repository_slug}
        else:
            message = "Repository not found"
            message_key = "errors.repository_not_found"
            message_params = {}
        super().__init__(message=message, message_key=message_key, message_params=message_params)


class PullRequestNotFoundException(NotFoundException):
    """Pull request not found"""

    def __init__(self, pull_request_id: str):
        super().__init__(
            message=f"Pull request with ID {pull_request_id} not found",
            message_key="errors.pull_request_not_found",
            message_params={"pull_request_id": pull_request_id},
        )


class TokenExpiredException(UnauthorizedException):
    """Token expired"""

    def __init__(self, message: str = "Token expired"):
        super().__init__(
            message=message,
            message_key="errors.token_expired",
        )


class InvalidTokenException(UnauthorizedException):
    """Invalid token"""

    def __init__(self, message: str = "Invalid token"):
        super().__init__(
            message=message,
            message_key="errors.token_invalid",
        )


class OperationNotAllowedException(BadRequestException):
    """Operation not allowed"""

    def __init__(self, operation: str, reason: str | None = None):
        message = f"Operation '{operation}' is not allowed"
        if reason:
            message += f": {reason}"
            message_key = "errors.operation_not_allowed_with_reason"
            message_params = {"operation": operation, "reason": reason}
        else:
            message_key = "errors.operation_not_allowed"
            message_params = {"operation": operation}
        super().__init__(message=message, message_key=message_key, message_params=message_params)


class GitServiceException(AppException):
    """Git service error"""

    def __init__(self, message: str = "Git service error"):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "git_service_error", "message": message},
            message_key="errors.git_service_error",
        )


class ErrorResponse(BaseModel):
    """Standard error response model"""

    error: str
    message: str
    detail: Any | None = None
