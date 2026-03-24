import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from src.core.config import settings


logger = logging.getLogger(__name__)

# 创建基类
Base = declarative_base()

# 全局数据库引擎
_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker | None = None


def get_engine() -> AsyncEngine:
    """获取数据库引擎"""
    global _engine
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    return _engine


def create_engine() -> AsyncEngine:
    """创建数据库引擎"""
    # 准备连接池相关参数（仅在使用非 NullPool 时需要）
    engine_kwargs = {
        "echo": settings.DEBUG,
        "pool_pre_ping": True,
        "connect_args": {
            "charset": "utf8mb4",
            "connect_timeout": settings.DATABASE_POOL_TIMEOUT,
        },
        "future": True,
    }

    # 根据是否使用 NullPool 来决定是否添加连接池参数
    # NullPool 不支持 pool_size, max_overflow, pool_timeout 等参数
    if settings.DATABASE_POOL_SIZE > 0:
        # 如果不使用 NullPool，可以添加连接池参数
        # 但异步引擎默认会使用 AsyncAdaptedQueuePool，所以这里不指定 poolclass
        engine_kwargs.update(
            {
                "pool_size": settings.DATABASE_POOL_SIZE,
                "max_overflow": settings.DATABASE_MAX_OVERFLOW,
                "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
                "pool_recycle": settings.DATABASE_POOL_RECYCLE,
            }
        )
    else:
        # 使用 NullPool 模式
        engine_kwargs["poolclass"] = NullPool

    engine = create_async_engine(settings.database_url, **engine_kwargs)
    return engine


async def init_db() -> None:
    """初始化数据库连接"""
    global _engine, _async_session_maker

    try:
        logger.info("Initializing database connection...")

        # 创建数据库引擎
        _engine = create_engine()

        # 创建会话工厂
        _async_session_maker = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        # 测试数据库连接
        async with _engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        logger.info("Database connection initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize database connection: {str(e)}", exc_info=True)
        raise


async def close_db() -> None:
    """关闭数据库连接"""
    global _engine, _async_session_maker

    try:
        if _engine is None:
            return

        logger.info("Closing database connection...")

        # 关闭数据库引擎
        await _engine.dispose()

        # 重置全局变量
        _engine = None
        _async_session_maker = None

        logger.info("Database connection closed successfully")

    except Exception as e:
        logger.error(f"Error closing database connection: {str(e)}", exc_info=True)
        raise


def get_session_maker() -> async_sessionmaker:
    """获取会话工厂"""
    global _async_session_maker
    if _async_session_maker is None:
        raise RuntimeError("Session maker not initialized. Call init_db() first.")
    return _async_session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的依赖注入函数
    用于FastAPI的Depends
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的上下文管理器
    用于需要手动管理会话的情况
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class DatabaseManager:
    """数据库管理器类"""

    def __init__(self):
        self.engine: AsyncEngine | None = None
        self.session_maker: async_sessionmaker | None = None

    async def initialize(self) -> None:
        """初始化数据库"""
        if self.engine is not None:
            logger.warning("Database already initialized")
            return

        logger.info("Initializing database manager...")

        # 创建引擎
        self.engine = create_engine()

        # 创建会话工厂
        self.session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        logger.info("Database manager initialized successfully")

    async def close(self) -> None:
        """关闭数据库连接"""
        if self.engine is None:
            return

        logger.info("Closing database manager...")

        await self.engine.dispose()

        self.engine = None
        self.session_maker = None

        logger.info("Database manager closed successfully")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话"""
        if self.session_maker is None:
            raise RuntimeError("Database manager not initialized. Call initialize() first.")

        async with self.session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def session_context(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话的上下文管理器"""
        if self.session_maker is None:
            raise RuntimeError("Database manager not initialized. Call initialize() first.")

        async with self.session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


# 全局数据库管理器实例
db_manager = DatabaseManager()
