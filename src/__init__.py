# Pull Request Code Review System
# FastAPI-based Pull Request Code Review System

__version__ = "1.0.0"
__author__ = "CodeGeeX"
__description__ = "FastAPI-based Pull Request Code Review System with MySQL, Redis, and Prometheus integration"

# Import main components for easy access
from src.main import app
from src.core.config import settings, get_settings
from src.core.database import Base, get_db_session
from src.core.exceptions import (
    AppException,
    ErrorCode,
    BadRequestException,
    ValidationException,
    UnauthorizedException,
    ForbiddenException,
    NotFoundException,
    ResourceAlreadyExistsException,
    InternalServerException,
    DatabaseException,
    CacheException,
    RateLimitException,
)

__all__ = [
    # Version
    "__version__",
    "__author__",
    "__description__",
    # Main app
    "app",
    # Config
    "settings",
    "get_settings",
    # Database
    "Base",
    "get_db_session",
    # Exceptions
    "AppException",
    "ErrorCode",
    "BadRequestException",
    "ValidationException",
    "UnauthorizedException",
    "ForbiddenException",
    "NotFoundException",
    "ResourceAlreadyExistsException",
    "InternalServerException",
    "DatabaseException",
    "CacheException",
    "RateLimitException",
]