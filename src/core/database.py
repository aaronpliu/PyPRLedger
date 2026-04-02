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

# Create base class
Base = declarative_base()

# Global database engine
_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker | None = None


def get_engine() -> AsyncEngine:
    """Get database engine"""
    global _engine
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    return _engine


def create_engine() -> AsyncEngine:
    """Create database engine"""
    # Prepare connection pool related parameters (only needed when not using NullPool)
    engine_kwargs = {
        "echo": settings.DEBUG,
        "pool_pre_ping": True,
        "connect_args": {
            "charset": "utf8mb4",
            "connect_timeout": settings.DATABASE_POOL_TIMEOUT,
        },
        "future": True,
    }

    # Decide whether to add connection pool parameters based on whether NullPool is used
    # NullPool does not support pool_size, max_overflow, pool_timeout and other parameters
    if settings.DATABASE_POOL_SIZE > 0:
        # If not using NullPool, can add connection pool parameters
        # But async engine will use AsyncAdaptedQueuePool by default, so we don't specify poolclass here
        engine_kwargs.update(
            {
                "pool_size": settings.DATABASE_POOL_SIZE,
                "max_overflow": settings.DATABASE_MAX_OVERFLOW,
                "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
                "pool_recycle": settings.DATABASE_POOL_RECYCLE,
            }
        )
    else:
        # Use NullPool mode
        engine_kwargs["poolclass"] = NullPool

    engine = create_async_engine(settings.database_url, **engine_kwargs)
    return engine


async def init_db() -> None:
    """Initialize database connection"""
    global _engine, _async_session_maker

    try:
        logger.info("Initializing database connection...")

        # Create database engine
        _engine = create_engine()

        # Create session factory
        _async_session_maker = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        # Test database connection
        async with _engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        logger.info("Database connection initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize database connection: {str(e)}", exc_info=True)
        raise


async def close_db() -> None:
    """Close database connection"""
    global _engine, _async_session_maker

    try:
        if _engine is None:
            return

        logger.info("Closing database connection...")

        # Close database engine
        await _engine.dispose()

        # Reset global variables
        _engine = None
        _async_session_maker = None

        logger.info("Database connection closed successfully")

    except Exception as e:
        logger.error(f"Error closing database connection: {str(e)}", exc_info=True)
        raise


def get_session_maker() -> async_sessionmaker:
    """Get session factory"""
    global _async_session_maker
    if _async_session_maker is None:
        raise RuntimeError("Session maker not initialized. Call init_db() first.")
    return _async_session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session dependency injection function
    Used for FastAPI's Depends
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
    Get database session context manager
    Used for situations requiring manual session management
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
    """Database manager class"""

    def __init__(self):
        self.engine: AsyncEngine | None = None
        self.session_maker: async_sessionmaker | None = None

    async def initialize(self) -> None:
        """Initialize database"""
        if self.engine is not None:
            logger.warning("Database already initialized")
            return

        logger.info("Initializing database manager...")

        # Create engine
        self.engine = create_engine()

        # Create session factory
        self.session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        logger.info("Database manager initialized successfully")

    async def close(self) -> None:
        """Close database connection"""
        if self.engine is None:
            return

        logger.info("Closing database manager...")

        await self.engine.dispose()

        self.engine = None
        self.session_maker = None

        logger.info("Database manager closed successfully")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session"""
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
        """Get database session context manager"""
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


# Global database manager instance
db_manager = DatabaseManager()
