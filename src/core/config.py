from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration class"""

    model_config = SettingsConfigDict(
        case_sensitive=True, env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Basic project information
    PROJECT_NAME: str = "Pull Request Code Review Result Storage System"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Environment configuration
    ENV: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")

    # Database configuration
    DATABASE_HOST: str = Field(default="localhost")
    DATABASE_PORT: int = Field(default=3306)
    DATABASE_USER: str = Field(default="root")
    DATABASE_PASSWORD: str = Field(default="")
    DATABASE_NAME: str = Field(default="code_review")
    DATABASE_POOL_SIZE: int = Field(default=20)
    DATABASE_MAX_OVERFLOW: int = Field(default=10)
    DATABASE_POOL_TIMEOUT: int = Field(default=30)
    DATABASE_POOL_RECYCLE: int = Field(default=3600)

    @property
    def database_url(self) -> str:
        """Get database connection URL"""
        return f"mysql+aiomysql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"

    # Redis configuration
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: str | None = Field(default=None)
    REDIS_DB: int = Field(default=0)
    REDIS_MAX_CONNECTIONS: int = Field(default=50)

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL"""
        password_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{password_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Redis cache TTL settings (seconds)
    CACHE_TTL_REVIEWS: int = Field(default=3600)
    CACHE_TTL_PROJECTS: int = Field(default=21600)
    CACHE_TTL_USERS: int = Field(default=43200)
    CACHE_TTL_STATS: int = Field(default=3600)

    # Security configuration
    SECRET_KEY: str = Field(default="development-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)

    # CORS configuration
    BACKEND_CORS_ORIGINS: str = Field(
        default="http://localhost:63342,http://127.0.0.1:63342",  # Allow JetBrains IDE preview and development origins
    )

    @computed_field
    @property
    def backend_cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string to list"""
        if isinstance(self.BACKEND_CORS_ORIGINS, str):
            # Handle wildcard for development
            if self.BACKEND_CORS_ORIGINS == "*":
                return ["*"]
            return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",")]
        # Fallback: should not happen given the field type, but handle gracefully
        return []

    # API rate limiting configuration
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_MAX_REQUESTS: int = Field(default=1000)
    RATE_LIMIT_PERIOD_SECONDS: int = Field(default=60)

    # Concurrency control configuration
    MAX_CONCURRENT_OPERATIONS: int = Field(default=1000)
    DB_QUERY_TIMEOUT: int = Field(default=30)

    # Prometheus monitoring configuration
    PROMETHEUS_ENABLED: bool = Field(default=True)
    PROMETHEUS_METRICS_PATH: str = Field(default="/metrics")

    # Pagination defaults
    DEFAULT_PAGE_SIZE: int = Field(default=20)
    MAX_PAGE_SIZE: int = Field(default=100)

    # Git configuration
    GIT_MAX_DIFF_SIZE: int = Field(default=1048576)
    GIT_MAX_FILES_IN_PR: int = Field(default=100)

    # Code review configuration
    REVIEW_MIN_SCORE: int = Field(default=0)
    REVIEW_MAX_SCORE: int = Field(default=10)

    # Bitbucket API configuration
    BITBUCKET_CLOUD: bool = Field(
        default=False,
        description="Whether to use Bitbucket Cloud (True) or Server/Data Center (False)",
    )
    BITBUCKET_SERVER_URL: str = Field(
        default="http://localhost:7990", description="Bitbucket Server/Data Center base URL"
    )
    BITBUCKET_USER: str | None = Field(
        default=None, description="Bitbucket username for authentication"
    )
    BITBUCKET_PASSWORD: str | None = Field(
        default=None, description="Bitbucket password or app password for authentication"
    )
    BITBUCKET_DEFAULT_WORKSPACE: str = Field(
        default="default", description="Default workspace/project key for Bitbucket repositories"
    )

    # Review status constants
    REVIEW_STATUS_OPEN: str = "open"
    REVIEW_STATUS_MERGED: str = "merged"
    REVIEW_STATUS_CLOSED: str = "closed"
    REVIEW_STATUS_DRAFT: str = "draft"

    @property
    def review_statuses(self) -> list[str]:
        """All valid review statuses"""
        return [
            self.REVIEW_STATUS_OPEN,
            self.REVIEW_STATUS_MERGED,
            self.REVIEW_STATUS_CLOSED,
            self.REVIEW_STATUS_DRAFT,
        ]

    # Task processing configuration
    TASK_QUEUE_ENABLED: bool = Field(default=True)
    MAX_RETRIES: int = Field(default=3)


@lru_cache
def get_settings() -> Settings:
    """Get singleton configuration instance"""
    return Settings()


settings = get_settings()
