import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from src.core.config import settings
from src.utils.metrics import metrics


logger = logging.getLogger(__name__)

# Create base class
Base = declarative_base()

# Global database engine
_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker | None = None


def _is_disconnected_error(e: Exception) -> bool:
    """Check if the given exception is a disconnected error"""
    return isinstance(e, DBAPIError) and bool(e.connection_invalidated)


def _extract_operation(clause: Any) -> str:
    """
    Extract the SQL operation type from a SQLAlchemy clause.

    Args:
        clause: The SQLAlchemy clause statement.

    Returns:
        str: Operation type (SELECT, INSERT, UPDATE, DELETE, or unknown).
    """
    clause_str = str(clause).strip().upper()
    for op in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        if clause_str.startswith(op):
            return op
    return "unknown"


def _extract_table(clause: Any) -> str:
    """
    Best-effort extraction of the first table name from a SQLAlchemy clause.

    For simple statements, parses the FROM/JOIN/INTO clauses.
    Falls back to 'unknown' when parsing is ambiguous.

    Args:
        clause: The SQLAlchemy clause statement.

    Returns:
        str: Table name or 'unknown'.
    """
    clause_str = str(clause).strip()
    upper_str = clause_str.upper()

    if upper_str.startswith("SELECT"):
        # Look for FROM ... JOIN pattern
        from_idx = upper_str.find("FROM ")
        if from_idx >= 0:
            after_from = clause_str[from_idx + 5 :].strip()
            # Take the first identifier (before space, comma, JOIN, WHERE, etc.)
            for delim in (" ", ",", "\n", "\t", "JOIN", "WHERE", "ORDER", "GROUP", "LIMIT"):
                idx = _find_non_quoted(after_from, delim)
                if idx >= 0:
                    return after_from[:idx].strip().strip('"').strip("`")
            return after_from.strip().strip('"').strip("`")
    elif upper_str.startswith("INSERT"):
        into_idx = upper_str.find("INTO ")
        if into_idx >= 0:
            after_into = clause_str[into_idx + 5 :].strip()
            space_idx = _find_non_quoted(after_into, " ")
            return (
                after_into[:space_idx].strip().strip('"').strip("`")
                if space_idx >= 0
                else after_into.strip().strip('"').strip("`")
            )
    elif upper_str.startswith("UPDATE"):
        # UPDATE table_name SET ...
        after_update = clause_str[6:].strip()
        space_idx = _find_non_quoted(after_update, " ")
        return (
            after_update[:space_idx].strip().strip('"').strip("`")
            if space_idx >= 0
            else after_update.strip().strip('"').strip("`")
        )
    elif upper_str.startswith("DELETE"):
        from_idx = upper_str.find("FROM ")
        if from_idx >= 0:
            after_from = clause_str[from_idx + 5 :].strip()
            space_idx = _find_non_quoted(after_from, " ")
            return (
                after_from[:space_idx].strip().strip('"').strip("`")
                if space_idx >= 0
                else after_from.strip().strip('"').strip("`")
            )
        # Also check for DELETE table_name WHERE ...
        after_delete = clause_str[6:].strip()
        space_idx = _find_non_quoted(after_delete, " ")
        if space_idx >= 0 and after_delete[:space_idx].upper() != "FROM":
            return after_delete[:space_idx].strip().strip('"').strip("`")
    return "unknown"


def _find_non_quoted(text: str, delim: str) -> int:
    """
    Find the first occurrence of a delimiter that is not inside quotes.

    Args:
        text: The text to search.
        delim: The delimiter to find.

    Returns:
        int: Index of the delimiter, or -1 if not found.
    """
    in_quote = False
    quote_char = None
    for i, ch in enumerate(text):
        if in_quote:
            if ch == quote_char:
                in_quote = False
        else:
            if ch in ('"', "`", "'"):
                in_quote = True
                quote_char = ch
            elif text[i : i + len(delim)] == delim:
                return i
    return -1


def _register_db_metric_listeners(engine: AsyncEngine) -> None:
    """
    Register SQLAlchemy event listeners on an engine to track database metrics.

    Listens for ``before_execute`` / ``after_execute`` to count queries and
    observe durations, and pool ``checkout`` to track active connections.

    Args:
        engine: The SQLAlchemy async engine to instrument.
    """
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_execute")
    def receive_before_execute(conn, clause, multiparams, params, execution_options):
        conn.info["_query_start_time"] = time.monotonic()

    @event.listens_for(sync_engine, "after_execute")
    def receive_after_execute(conn, clause, multiparams, params, execution_options, result):
        operation = _extract_operation(clause)
        table = _extract_table(clause)
        metrics.increment_db_query(operation=operation, table=table)
        start_time = conn.info.pop("_query_start_time", None)
        if start_time is not None:
            duration = time.monotonic() - start_time
            metrics.observe_db_query_duration(operation=operation, duration=duration)

    # Pool events are only meaningful when using a connection pool (not NullPool)
    if not isinstance(sync_engine.pool, NullPool):
        sync_pool = sync_engine.pool

        @event.listens_for(sync_pool, "checkout")
        def receive_checkout(dbapi_conn, conn_record, conn_proxy):
            metrics.set_db_connections_active(sync_pool.checkedin())


def get_engine() -> AsyncEngine:
    """Get database engine"""
    global _engine
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    return _engine


def create_engine() -> AsyncEngine:
    """Create database engine"""

    drivername = make_url(settings.database_url).drivername
    # Prepare connection pool related parameters (only needed when not using NullPool)
    engine_kwargs = {
        "echo": settings.DEBUG,
        "pool_use_lifo": True,
        "connect_args": {
            "charset": "utf8mb4",
            "connect_timeout": settings.DATABASE_POOL_TIMEOUT,
        },
        "future": True,
    }

    # Add connection arguments based on the driver name
    if drivername == "pymysql" or drivername == "mysql+aiomysql" or drivername == "mysql+asyncmy":
        engine_kwargs["connect_args"]["charset"] = "utf8mb4"
    elif drivername == "postgresql+asyncpg":
        engine_kwargs["connect_args"]["options"] = (
            f"-c statement_timeout={settings.DATABASE_POOL_TIMEOUT * 1000}"
        )

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
    _register_db_metric_listeners(engine)
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
        except Exception as exc:
            await session.rollback()
            if _is_disconnected_error(exc):
                logger.warning(
                    "Database connection is disconnected. The pool will replace it on next checkout."
                )
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
        except Exception as exc:
            await session.rollback()
            if _is_disconnected_error(exc):
                logger.warning(
                    "Database connection is disconnected. The pool will replace it on next checkout."
                )
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
            except Exception as exc:
                await session.rollback()
                if _is_disconnected_error(exc):
                    logger.warning("Database connection is disconnected. Reconnecting...")
                    await self.engine.dispose()
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
            except Exception as exc:
                await session.rollback()
                if _is_disconnected_error(exc):
                    logger.warning("Database connection is disconnected. Reconnecting...")
                    await self.engine.dispose()
                raise
            finally:
                await session.close()


# Global database manager instance
db_manager = DatabaseManager()
