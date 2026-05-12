"""Timezone utility functions for consistent datetime handling across the application

This module provides utilities for:
- Getting current time in configured timezone
- Converting between UTC and local timezone
- Ensuring all datetime operations respect the application's timezone configuration
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from src.core.config import settings


@lru_cache(maxsize=1)
def get_local_timezone() -> ZoneInfo:
    """Get the configured local timezone (cached for performance)

    Returns:
        ZoneInfo: The timezone object based on TIMEZONE setting
    """
    try:
        return ZoneInfo(settings.TIMEZONE)
    except Exception as e:
        # Fallback to UTC if timezone is invalid
        from src.utils.log import get_logger

        logger = get_logger(__name__)
        logger.warning(f"Invalid timezone '{settings.TIMEZONE}': {e}. Falling back to UTC.")
        return ZoneInfo("UTC")


def get_current_time() -> datetime:
    """Get current time in the configured timezone

    If USE_UTC_IN_DB is True, returns UTC time (for database storage).
    Otherwise, returns time in the configured local timezone.

    Returns:
        datetime: Current timezone-aware datetime
    """
    if settings.USE_UTC_IN_DB:
        return datetime.now(UTC)
    else:
        return datetime.now(get_local_timezone())


@lru_cache(maxsize=1)
def _get_use_utc_in_db() -> bool:
    """Get cached USE_UTC_IN_DB setting (cached for performance)"""
    return settings.USE_UTC_IN_DB


def convert_to_timezone(dt: datetime, tz_name: str | None = None) -> datetime:
    """Convert a datetime to specified timezone

    Args:
        dt: The datetime to convert (timezone-aware or naive)
        tz_name: Target timezone name (defaults to configured TIMEZONE)

    Returns:
        datetime: Converted timezone-aware datetime

    Note:
        If dt is naive (no timezone info), it will be assumed to be UTC.
    """
    target_tz = ZoneInfo(tz_name or settings.TIMEZONE)

    # If datetime is naive, assume it's UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    return dt.astimezone(target_tz)


def utc_to_local(dt: datetime) -> datetime:
    """Convert datetime to local timezone for display

    This function handles both scenarios:
    1. If USE_UTC_IN_DB=True: Converts UTC → Local timezone
    2. If USE_UTC_IN_DB=False: Ensures datetime has proper timezone info (pass-through if already correct)

    Args:
        dt: Datetime from database (timezone-aware or naive)

    Returns:
        datetime: Local timezone datetime ready for display

    Note:
        - If dt is naive, it will be assumed to match the database timezone setting
        - When USE_UTC_IN_DB=False, naive datetimes are assumed to be in local timezone
        - When USE_UTC_IN_DB=True, naive datetimes are assumed to be UTC
    """
    # Use cached values for performance
    use_utc = _get_use_utc_in_db()
    local_tz = get_local_timezone()

    # If datetime is naive, assign timezone based on DB configuration
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC) if use_utc else dt.replace(tzinfo=local_tz)

    # Convert to local timezone if needed
    if use_utc:
        # DB stores UTC, convert to local
        return dt.astimezone(local_tz)
    else:
        # DB already stores local time, just ensure it's in the right timezone
        if dt.tzinfo != local_tz:
            return dt.astimezone(local_tz)
        return dt


def local_to_utc(dt: datetime) -> datetime:
    """Convert local timezone datetime to UTC

    This function handles both scenarios:
    1. If USE_UTC_IN_DB=True: Local → UTC conversion (for DB storage)
    2. If USE_UTC_IN_DB=False: Returns as-is (DB stores local time)

    Args:
        dt: Local timezone datetime (timezone-aware)

    Returns:
        datetime: UTC datetime (if USE_UTC_IN_DB=True) or original datetime
    """
    if settings.USE_UTC_IN_DB:
        return convert_to_timezone(dt, "UTC")
    else:
        # DB stores local time, no conversion needed
        return dt


def format_datetime(
    dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S", tz_name: str | None = None
) -> str:
    """Format datetime to string in specified timezone

    Args:
        dt: The datetime to format
        fmt: Format string (default: "%Y-%m-%d %H:%M:%S")
        tz_name: Timezone for formatting (defaults to configured TIMEZONE)

    Returns:
        str: Formatted datetime string
    """
    if tz_name:
        dt = convert_to_timezone(dt, tz_name)
    return dt.strftime(fmt)


def parse_datetime(
    date_str: str, fmt: str = "%Y-%m-%d %H:%M:%S", tz_name: str | None = None
) -> datetime:
    """Parse datetime string to timezone-aware datetime

    Args:
        date_str: The datetime string to parse
        fmt: Format string (default: "%Y-%m-%d %H:%M:%S")
        tz_name: Timezone to assign (defaults to configured TIMEZONE)

    Returns:
        datetime: Parsed timezone-aware datetime
    """
    dt = datetime.strptime(date_str, fmt)
    target_tz = ZoneInfo(tz_name or settings.TIMEZONE)
    return dt.replace(tzinfo=target_tz)
