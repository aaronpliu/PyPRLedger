from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from pydantic import BaseModel


class ErrorCode:
    """错误码常量"""
    
    # 通用错误 (1000-1999)
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    
    # 请求相关错误 (2000-2999)
    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    
    # 认证和授权错误 (3000-3999)
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    
    # 资源相关错误 (4000-4999)
    NOT_FOUND = "NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    RESOURCE_LOCKED = "RESOURCE_LOCKED"
    
    # 业务逻辑错误 (5000-5999)
    INVALID_OPERATION = "INVALID_OPERATION"
    INVALID_STATUS = "INVALID_STATUS"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"
    
    # 数据库错误 (6000-6999)
    DATABASE_ERROR = "DATABASE_ERROR"
    DATABASE_CONNECTION_ERROR = "DATABASE_CONNECTION_ERROR"
    DATABASE_TIMEOUT = "DATABASE_TIMEOUT"
    
    # 缓存错误 (7000-7999)
    CACHE_ERROR = "CACHE_ERROR"
    CACHE_CONNECTION_ERROR = "CACHE_CONNECTION_ERROR"
    CACHE_MISS = "CACHE_MISS"
    
    # 外部服务错误 (8000-8999)
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    GIT_SERVICE_ERROR = "GIT_SERVICE_ERROR"
    
    # 限流错误 (9000-9999)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


class AppException(HTTPException):
    """应用程序基础异常类"""
    
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: Optional[Any] = None
    ):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(status_code=status_code, detail=message)


class BadRequestException(AppException):
    """400 Bad Request"""
    
    def __init__(self, message: str = "Bad request", detail: Optional[Any] = None):
        super().__init__(
            code=ErrorCode.BAD_REQUEST,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


class ValidationException(AppException):
    """422 Validation Error"""
    
    def __init__(self, message: str = "Validation failed", detail: Optional[Any] = None):
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail
        )


class UnauthorizedException(AppException):
    """401 Unauthorized"""
    
    def __init__(self, message: str = "Unauthorized", detail: Optional[Any] = None):
        super().__init__(
            code=ErrorCode.UNAUTHORIZED,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail
        )


class ForbiddenException(AppException):
    """403 Forbidden"""
    
    def __init__(self, message: str = "Access forbidden", detail: Optional[Any] = None):
        super().__init__(
            code=ErrorCode.FORBIDDEN,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class NotFoundException(AppException):
    """404 Not Found"""
    
    def __init__(self, message: str = "Resource not found", detail: Optional[Any] = None):
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )


class ResourceAlreadyExistsException(AppException):
    """409 Conflict - Resource Already Exists"""
    
    def __init__(self, message: str = "Resource already exists", detail: Optional[Any] = None):
        super().__init__(
            code=ErrorCode.RESOURCE_ALREADY_EXISTS,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            detail=detail
        )


class InternalServerException(AppException):
    """500 Internal Server Error"""
    
    def __init__(self, message: str = "Internal server error", detail: Optional[Any] = None):
        super().__init__(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


class DatabaseException(AppException):
    """Database related errors"""
    
    def __init__(self, message: str = "Database error", detail: Optional[Any] = None):
        super().__init__(
            code=ErrorCode.DATABASE_ERROR,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


class DatabaseConnectionException(AppException):
    """Database connection error"""
    
    def __init__(self, message: str = "Database connection error", detail: Optional[Any] = None):
        super().__init__(
            code=ErrorCode.DATABASE_CONNECTION_ERROR,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail
        )


class CacheException(AppException):
    """Cache related errors"""
    
    def __init__(self, message: str = "Cache error", detail: Optional[Any] = None):
        super().__init__(
            code=ErrorCode.CACHE_ERROR,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


class RateLimitException(AppException):
    """Rate limit exceeded"""
    
    def __init__(self, message: str = "Rate limit exceeded", detail: Optional[Any] = None):
        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail
        )


class ReviewNotFoundException(NotFoundException):
    """Review not found"""
    
    def __init__(self, review_id: str):
        super().__init__(message=f"Review with ID {review_id} not found", detail={"review_id": review_id})


class ReviewAlreadyExistsException(ResourceAlreadyExistsException):
    """Review already exists"""
    
    def __init__(self, review_id: str):
        super().__init__(message=f"Review with ID {review_id} already exists", detail={"review_id": review_id})


class InvalidReviewDataException(BadRequestException):
    """Invalid review data"""
    
    def __init__(self, message: str = "Invalid review data", detail: Optional[Any] = None):
        super().__init__(message=message, detail=detail)


class ReviewStatusException(BadRequestException):
    """Invalid review status"""
    
    def __init__(self, current_status: str, target_status: str, message: Optional[str] = None):
        detail = {
            "current_status": current_status,
            "target_status": target_status
        }
        message = message or f"Cannot transition review from {current_status} to {target_status}"
        super().__init__(message=message, detail=detail)


class UserNotFoundException(NotFoundException):
    """User not found"""
    
    def __init__(self, user_id: Optional[int] = None, username: Optional[str] = None):
        if user_id:
            message = f"User with ID {user_id} not found"
            detail = {"user_id": user_id}
        elif username:
            message = f"User with username '{username}' not found"
            detail = {"username": username}
        else:
            message = "User not found"
            detail = None
        super().__init__(message=message, detail=detail)


class UserAlreadyExistsException(ResourceAlreadyExistsException):
    """User already exists"""
    
    def __init__(self, username: Optional[str] = None, email: Optional[str] = None):
        if username:
            message = f"User with username '{username}' already exists"
            detail = {"username": username}
        elif email:
            message = f"User with email '{email}' already exists"
            detail = {"email": email}
        else:
            message = "User already exists"
            detail = None
        super().__init__(message=message, detail=detail)


class ProjectNotFoundException(NotFoundException):
    """Project not found"""
    
    def __init__(self, project_id: Optional[int] = None, project_key: Optional[str] = None):
        if project_id:
            message = f"Project with ID {project_id} not found"
            detail = {"project_id": project_id}
        elif project_key:
            message = f"Project with key '{project_key}' not found"
            detail = {"project_key": project_key}
        else:
            message = "Project not found"
            detail = None
        super().__init__(message=message, detail=detail)


class RepositoryNotFoundException(NotFoundException):
    """Repository not found"""
    
    def __init__(self, repository_id: Optional[str] = None, repository_slug: Optional[str] = None):
        if repository_id:
            message = f"Repository with ID {repository_id} not found"
            detail = {"repository_id": repository_id}
        elif repository_slug:
            message = f"Repository with slug '{repository_slug}' not found"
            detail = {"repository_slug": repository_slug}
        else:
            message = "Repository not found"
            detail = None
        super().__init__(message=message, detail=detail)


class PullRequestNotFoundException(NotFoundException):
    """Pull request not found"""
    
    def __init__(self, pull_request_id: str):
        super().__init__(message=f"Pull request with ID {pull_request_id} not found", detail={"pull_request_id": pull_request_id})


class InvalidCredentialsException(UnauthorizedException):
    """Invalid credentials"""
    
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message=message)


class TokenExpiredException(UnauthorizedException):
    """Token expired"""
    
    def __init__(self, message: str = "Token expired"):
        super().__init__(code=ErrorCode.TOKEN_EXPIRED, message=message)


class InvalidTokenException(UnauthorizedException):
    """Invalid token"""
    
    def __init__(self, message: str = "Invalid token"):
        super().__init__(code=ErrorCode.TOKEN_INVALID, message=message)


class OperationNotAllowedException(BadRequestException):
    """Operation not allowed"""
    
    def __init__(self, operation: str, reason: Optional[str] = None):
        message = f"Operation '{operation}' is not allowed"
        if reason:
            message += f": {reason}"
        super().__init__(code=ErrorCode.OPERATION_NOT_ALLOWED, message=message)

class RepositoryNotFoundException(Exception):
    """Raised when a repository is not found"""
    
    def __init__(self, repository_id: str, message: str = None):
        self.repository_id = repository_id
        self.message = message or f"Repository not found: {repository_id}"
        super().__init__(self.message)

class GitServiceException(AppException):
    """Git service error"""
    
    def __init__(self, message: str = "Git service error", detail: Optional[Any] = None):
        super().__init__(
            code=ErrorCode.GIT_SERVICE_ERROR,
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail
        )


class ErrorResponse(BaseModel):
    """标准错误响应模型"""
    error: str
    message: str
    detail: Optional[Any] = None