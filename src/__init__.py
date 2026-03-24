import tomllib
from pathlib import Path


# Single source of truth: version is managed in pyproject.toml
def _get_version():
    """Get version from pyproject.toml file"""
    try:
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with Path.open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)
            return pyproject_data.get("project", {}).get("version", "1.0.0-dev")
    except Exception:
        # Fallback for any unexpected errors
        return "1.0.0-dev"


__version__ = _get_version()
__author__ = "Aaron P LIU"
__description__ = "FastAPI-based Pull Request Code Review Result Storage System with MySQL, Redis, and Prometheus integration"


# Lazy imports to avoid circular dependency issues
def __getattr__(name):
    """Lazy loading of module attributes"""
    if name == "app":
        from src.main import app

        return app
    elif name in ("settings", "get_settings"):
        from src.core.config import get_settings, settings

        return locals()[name]
    elif name == "Base":
        from src.core.database import Base

        return Base
    elif name == "get_db_session":
        from src.core.database import get_db_session

        return get_db_session
    elif name in (
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
    ):
        from src.core.exceptions import (
            AppException,
            BadRequestException,
            CacheException,
            DatabaseException,
            ErrorCode,
            ForbiddenException,
            InternalServerException,
            NotFoundException,
            RateLimitException,
            ResourceAlreadyExistsException,
            UnauthorizedException,
            ValidationException,
        )

        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
