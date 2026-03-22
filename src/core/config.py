import os
from functools import lru_cache
from typing import List, Optional
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用程序配置类"""

    model_config = SettingsConfigDict(
        case_sensitive=True, env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 项目基本信息
    PROJECT_NAME: str = "Pull Request Code Review Result Storage System"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # 环境配置
    ENV: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")

    # 数据库配置
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
    def DATABASE_URL(self) -> str:
        """获取数据库连接 URL"""
        return f"mysql+aiomysql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"

    # Redis 配置
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: Optional[str] = Field(default=None)
    REDIS_DB: int = Field(default=0)
    REDIS_MAX_CONNECTIONS: int = Field(default=50)

    @property
    def REDIS_URL(self) -> str:
        """获取 Redis 连接 URL"""
        password_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{password_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Redis 缓存 TTL 设置 (秒)
    CACHE_TTL_REVIEWS: int = Field(default=3600)
    CACHE_TTL_PROJECTS: int = Field(default=21600)
    CACHE_TTL_USERS: int = Field(default=43200)
    CACHE_TTL_STATS: int = Field(default=3600)

    # 安全配置
    SECRET_KEY: str = Field(default="development-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)

    # CORS 配置 - 使用字符串存储，通过 computed_field 解析为列表
    BACKEND_CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:8000")

    @computed_field
    @property
    def BACKEND_CORS_ORIGINS_LIST(self) -> List[str]:
        """Parse CORS origins from comma-separated string to list"""
        if isinstance(self.BACKEND_CORS_ORIGINS, str):
            return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",")]
        return self.BACKEND_CORS_ORIGINS

    # API 限流配置
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_MAX_REQUESTS: int = Field(default=1000)
    RATE_LIMIT_PERIOD_SECONDS: int = Field(default=60)

    # 并发控制配置
    MAX_CONCURRENT_OPERATIONS: int = Field(default=1000)
    DB_QUERY_TIMEOUT: int = Field(default=30)

    # Prometheus 监控配置
    PROMETHEUS_ENABLED: bool = Field(default=True)
    PROMETHEUS_METRICS_PATH: str = Field(default="/metrics")

    # 分页默认值
    DEFAULT_PAGE_SIZE: int = Field(default=20)
    MAX_PAGE_SIZE: int = Field(default=100)

    # Git 配置
    GIT_MAX_DIFF_SIZE: int = Field(default=1048576)
    GIT_MAX_FILES_IN_PR: int = Field(default=100)

    # 代码审查配置
    REVIEW_MIN_SCORE: int = Field(default=0)
    REVIEW_MAX_SCORE: int = Field(default=10)

    # 审查状态
    REVIEW_STATUS_OPEN: str = "open"
    REVIEW_STATUS_MERGED: str = "merged"
    REVIEW_STATUS_CLOSED: str = "closed"
    REVIEW_STATUS_DRAFT: str = "draft"

    @property
    def REVIEW_STATUSES(self) -> List[str]:
        """所有有效的审查状态"""
        return [
            self.REVIEW_STATUS_OPEN,
            self.REVIEW_STATUS_MERGED,
            self.REVIEW_STATUS_CLOSED,
            self.REVIEW_STATUS_DRAFT,
        ]

    # 任务处理配置
    TASK_QUEUE_ENABLED: bool = Field(default=True)
    MAX_RETRIES: int = Field(default=3)


@lru_cache()
def get_settings() -> Settings:
    """获取单例配置实例"""
    return Settings()


settings = get_settings()
