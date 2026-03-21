import os
from functools import lru_cache
from typing import List, Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用程序配置类"""
    
    # 项目基本信息
    PROJECT_NAME: str = "Pull Request Code Review System"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # 环境配置
    ENV: str = Field(default="development", env="ENV")
    DEBUG: bool = Field(default=False, env="DEBUG")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    # 数据库配置
    DATABASE_HOST: str = Field(default="localhost", env="DATABASE_HOST")
    DATABASE_PORT: int = Field(default=3306, env="DATABASE_PORT")
    DATABASE_USER: str = Field(default="root", env="DATABASE_USER")
    DATABASE_PASSWORD: str = Field(default="", env="DATABASE_PASSWORD")
    DATABASE_NAME: str = Field(default="code_review", env="DATABASE_NAME")
    DATABASE_POOL_SIZE: int = Field(default=20, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(default=10, env="DATABASE_MAX_OVERFLOW")
    DATABASE_POOL_TIMEOUT: int = Field(default=30, env="DATABASE_POOL_TIMEOUT")
    DATABASE_POOL_RECYCLE: int = Field(default=3600, env="DATABASE_POOL_RECYCLE")
    
    @property
    def DATABASE_URL(self) -> str:
        """获取数据库连接 URL"""
        return f"mysql+aiomysql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
    
    # Redis 配置
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    REDIS_MAX_CONNECTIONS: int = Field(default=50, env="REDIS_MAX_CONNECTIONS")
    
    @property
    def REDIS_URL(self) -> str:
        """获取 Redis 连接 URL"""
        password_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{password_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # Redis 缓存 TTL 设置 (秒)
    CACHE_TTL_REVIEWS: int = Field(default=3600, env="CACHE_TTL_REVIEWS")  # 1 小时
    CACHE_TTL_PROJECTS: int = Field(default=21600, env="CACHE_TTL_PROJECTS")  # 6 小时
    CACHE_TTL_USERS: int = Field(default=43200, env="CACHE_TTL_USERS")  # 12 小时
    CACHE_TTL_STATS: int = Field(default=3600, env="CACHE_TTL_STATS")  # 1 小时
    
    # 安全配置
    SECRET_KEY: str = Field(default="development-secret-key-change-in-production", env="SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # CORS 配置
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        env="BACKEND_CORS_ORIGINS"
    )
    
    @model_validator(mode='before')
    @classmethod
    def parse_cors_origins(cls, values):
        """Parse BACKEND_CORS_ORIGINS from comma-separated string to list"""
        if isinstance(values, dict):
            cors_origins = values.get('BACKEND_CORS_ORIGINS')
            if isinstance(cors_origins, str):
                # Parse comma-separated string to list
                values['BACKEND_CORS_ORIGINS'] = [origin.strip() for origin in cors_origins.split(',')]
        return values
    
    # API 限流配置
    RATE_LIMIT_ENABLED: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    RATE_LIMIT_MAX_REQUESTS: int = Field(default=1000, env="RATE_LIMIT_MAX_REQUESTS")
    RATE_LIMIT_PERIOD_SECONDS: int = Field(default=60, env="RATE_LIMIT_PERIOD_SECONDS")
    
    # 并发控制配置
    MAX_CONCURRENT_OPERATIONS: int = Field(default=1000, env="MAX_CONCURRENT_OPERATIONS")
    DB_QUERY_TIMEOUT: int = Field(default=30, env="DB_QUERY_TIMEOUT")
    
    # Prometheus 监控配置
    PROMETHEUS_ENABLED: bool = Field(default=True, env="PROMETHEUS_ENABLED")
    PROMETHEUS_METRICS_PATH: str = Field(default="/metrics", env="PROMETHEUS_METRICS_PATH")
    
    # 分页默认值
    DEFAULT_PAGE_SIZE: int = Field(default=20, env="DEFAULT_PAGE_SIZE")
    MAX_PAGE_SIZE: int = Field(default=100, env="MAX_PAGE_SIZE")
    
    # Git 配置
    GIT_MAX_DIFF_SIZE: int = Field(default=1048576, env="GIT_MAX_DIFF_SIZE")  # 1MB
    GIT_MAX_FILES_IN_PR: int = Field(default=100, env="GIT_MAX_FILES_IN_PR")
    
    # 代码审查配置
    REVIEW_MIN_SCORE: int = Field(default=0, env="REVIEW_MIN_SCORE")
    REVIEW_MAX_SCORE: int = Field(default=10, env="REVIEW_MAX_SCORE")
    
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
            self.REVIEW_STATUS_DRAFT
        ]
    
    # 任务处理配置
    TASK_QUEUE_ENABLED: bool = Field(default=True, env="TASK_QUEUE_ENABLED")
    MAX_RETRIES: int = Field(default=3, env="MAX_RETRIES")
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取单例配置实例"""
    return Settings()


settings = get_settings()
