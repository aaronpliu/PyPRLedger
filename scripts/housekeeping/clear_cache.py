#!/usr/bin/env python3
"""
Deployment Cache Clearing Script

This script clears all Redis caches when deploying a new version to prevent
issues caused by model or schema changes resulting in data inconsistencies.

Usage:
    python3 clear_cache.py --all                    # Clear all caches
    python3 clear_cache.py --type users             # Clear specific cache type
    python3 clear_cache.py --all --dry-run          # Preview what will be deleted
    python3 clear_cache.py --type reviews --limit 100  # Limit deletion count

Author: PyPRLedger Team
Date: 2026-04-03
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from redis.asyncio import Redis


# Add parent directory to path to import project modules
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.log import get_logger, setup_logging
from src.utils.redis import close_redis, get_redis_client, init_redis


# Setup logging using project's standard configuration
LOG_CONFIG_PATH = PROJECT_ROOT / "src" / "conf" / "logging.yaml"
LOG_DIR = PROJECT_ROOT / "logs"

# Ensure log directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Initialize logging
setup_logging(config_path=str(LOG_CONFIG_PATH))

logger = get_logger("cache_clearer")


class CacheClearer:
    """Redis cache clearing utility for deployment"""

    # Cache key patterns by type
    CACHE_PATTERNS = {
        "users": [
            "user:*",  # user:{id}
            "user:username:*",  # user:username:{username}
            "user:email:*",  # user:email:{email}
            "users:list:*",  # users:list:{filters}:{page}:{page_size}
        ],
        "projects": [
            "project:*",  # project:{id}, project:{id}:repo_count, project:{id}:review_count, project:{id}:active_reviewer_count
            "project:key:*",  # project:key:{project_key}
            "project_key:*",  # project_key:{key} (legacy)
            "project_name:*",  # project_name:{name} (legacy)
            "projects:list:*",  # projects:list:{filters}:{page}:{page_size}
            "stats:projects:*",  # stats:projects:{project_id or 'all'}
        ],
        "repositories": [
            "repo:*",  # repo:{id}
            "repo_key:*",  # repo_key:{key}
        ],
        "reviews": [
            "review:*",  # review:{project_key}:{repo_slug}:{pr_id}
            "reviews:list:*",  # reviews:list:{filters}:{page}:{page_size}
            "stats:reviews:*",  # stats:reviews:{project_key or 'all'}
        ],
        "scores": [
            "scores:*",  # scores:{project_key}:{repo_slug}:{pr_id}:{file_part}
        ],
        "registry": [
            "registry:*",  # registry:{project_key}:{repo_slug}
        ],
    }

    def __init__(self, redis_client: Redis):
        """Initialize with Redis client

        Args:
            redis_client: Redis client instance
        """
        self.redis_client = redis_client
        self.deleted_count = 0
        self.error_count = 0

    async def get_keys_by_pattern(self, pattern: str, limit: int = 10000) -> list[str]:
        """Get all keys matching a pattern using SCAN

        Args:
            pattern: Redis key pattern (supports * wildcard)
            limit: Maximum number of keys to return

        Returns:
            List of matching keys
        """
        try:
            keys = []
            cursor = 0
            while True:
                cursor, batch = await self.redis_client.scan(
                    cursor=cursor, match=pattern, count=min(limit - len(keys), 1000)
                )
                keys.extend(batch)

                if cursor == 0 or len(keys) >= limit:
                    break

            return keys[:limit]
        except Exception as e:
            logger.error(f"Error scanning keys with pattern '{pattern}': {e}")
            self.error_count += 1
            return []

    async def delete_keys(self, keys: list[str], dry_run: bool = False) -> int:
        """Delete multiple keys in batches

        Args:
            keys: List of keys to delete
            dry_run: If True, only log what would be deleted

        Returns:
            Number of keys deleted
        """
        if not keys:
            return 0

        if dry_run:
            logger.info(f"  [DRY-RUN] Would delete {len(keys)} keys")
            if len(keys) <= 10:
                for key in keys:
                    logger.info(f"    - {key}")
            else:
                for key in keys[:5]:
                    logger.info(f"    - {key}")
                logger.info(f"    ... and {len(keys) - 5} more")
            return len(keys)

        # Delete in batches of 1000
        batch_size = 1000
        deleted = 0

        for i in range(0, len(keys), batch_size):
            batch = keys[i : i + batch_size]
            try:
                result = await self.redis_client.delete(*batch)
                deleted += result
                logger.debug(f"Deleted batch {i // batch_size + 1}: {result} keys")
            except Exception as e:
                logger.error(f"Error deleting batch: {e}")
                self.error_count += 1

        return deleted

    async def clear_cache_type(
        self, cache_type: str, dry_run: bool = False, limit: int = 10000
    ) -> int:
        """Clear all caches of a specific type

        Args:
            cache_type: Type of cache to clear
            dry_run: If True, only preview deletion
            limit: Maximum keys to process per pattern

        Returns:
            Number of keys deleted/dry-run count
        """
        if cache_type not in self.CACHE_PATTERNS:
            logger.error(f"Unknown cache type: {cache_type}")
            logger.info(f"Available types: {', '.join(self.CACHE_PATTERNS.keys())}")
            return 0

        patterns = self.CACHE_PATTERNS[cache_type]
        total_deleted = 0

        logger.info(f"Clearing '{cache_type}' caches...")

        for pattern in patterns:
            logger.debug(f"Scanning pattern: {pattern}")
            keys = await self.get_keys_by_pattern(pattern, limit)

            if keys:
                logger.info(f"  Found {len(keys)} keys matching '{pattern}'")
                deleted = await self.delete_keys(keys, dry_run)
                total_deleted += deleted

        action = "Would delete" if dry_run else "Deleted"
        logger.info(f"  {action} {total_deleted} '{cache_type}' cache entries")

        return total_deleted

    async def clear_all_caches(self, dry_run: bool = False, limit: int = 10000) -> int:
        """Clear all caches

        Args:
            dry_run: If True, only preview deletion
            limit: Maximum keys to process per pattern

        Returns:
            Total number of keys deleted/dry-run count
        """
        logger.info("=" * 60)
        logger.info("CLEARING ALL CACHES")
        logger.info("=" * 60)

        total = 0
        for cache_type in self.CACHE_PATTERNS:
            deleted = await self.clear_cache_type(cache_type, dry_run, limit)
            total += deleted
            logger.info("")  # Empty line between types

        action = "Would delete" if dry_run else "Deleted"
        logger.info("=" * 60)
        logger.info(f"{action} TOTAL: {total} cache entries")
        logger.info("=" * 60)

        return total

    async def clear_specific_project(
        self, project_key: str, repository_slug: str | None = None, dry_run: bool = False
    ) -> int:
        """Clear caches for a specific project/repository

        Args:
            project_key: Project key to clear
            repository_slug: Optional repository slug (if None, clears all repos for project)
            dry_run: If True, only preview deletion

        Returns:
            Number of keys deleted/dry-run count
        """
        logger.info("=" * 60)
        logger.info(f"CLEARING CACHES FOR PROJECT: {project_key}")
        if repository_slug:
            logger.info(f"Repository: {repository_slug}")
        logger.info("=" * 60)

        # Build patterns
        patterns = [
            f"project_key:{project_key}",
            f"project_name:{project_key}",
            "list:projects:*",
        ]

        if repository_slug:
            patterns.append(f"repo_key:{project_key}/{repository_slug}")
            patterns.append(f"review:{project_key}:{repository_slug}:*")
        else:
            patterns.append(f"repo_key:{project_key}/*")
            patterns.append(f"review:{project_key}:*:*")

        total = 0
        for pattern in patterns:
            keys = await self.get_keys_by_pattern(pattern)
            if keys:
                logger.info(f"Found {len(keys)} keys matching '{pattern}'")
                deleted = await self.delete_keys(keys, dry_run)
                total += deleted

        action = "Would delete" if dry_run else "Deleted"
        logger.info(f"{action} {total} cache entries for project {project_key}")

        return total


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Clear Redis caches during deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --all                        Clear all caches
  %(prog)s --type users                 Clear only user caches
  %(prog)s --type projects,reviews      Clear multiple types
  %(prog)s --all --dry-run              Preview what will be deleted
  %(prog)s --project-key myapp          Clear specific project
  %(prog)s --project-key myapp --repo-slug backend  Clear specific repo
        """,
    )

    parser.add_argument("--all", "-a", action="store_true", help="Clear all caches")

    parser.add_argument(
        "--type",
        "-t",
        type=str,
        help="Comma-separated cache types to clear (users,projects,repositories,reviews,scores,registry)",
    )

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Preview what will be deleted without actually deleting",
    )

    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=10000,
        help="Maximum keys to process per pattern (default: 10000)",
    )

    parser.add_argument("--project-key", type=str, help="Clear caches for specific project key")

    parser.add_argument(
        "--repo-slug",
        type=str,
        help="Clear caches for specific repository slug (use with --project-key)",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.all and not args.type and not args.project_key:
        parser.print_help()
        print("\nError: Must specify --all, --type, or --project-key")
        sys.exit(1)

    if args.project_key and args.all:
        print("Error: Cannot use --project-key with --all")
        sys.exit(1)

    try:
        # Initialize Redis using project's standard initialization
        logger.info("Initializing Redis connection...")
        await init_redis()
        logger.info("✅ Redis connection established")

        # Get Redis client
        redis_client = get_redis_client()

        # Initialize clearer with the client
        clearer = CacheClearer(redis_client)

        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("CACHE CLEARING OPERATION STARTED")
        logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Mode: {'DRY-RUN' if args.dry_run else 'ACTUAL DELETION'}")
        logger.info("=" * 60)
        logger.info("")

        # Execute clearing
        if args.project_key:
            total = await clearer.clear_specific_project(
                args.project_key, args.repo_slug, args.dry_run
            )
        elif args.all:
            total = await clearer.clear_all_caches(args.dry_run, args.limit)
        else:
            cache_types = [t.strip() for t in args.type.split(",")]
            total = 0
            logger.info("=" * 60)
            logger.info("CLEARING SPECIFIC CACHE TYPES")
            logger.info("=" * 60)
            for cache_type in cache_types:
                deleted = await clearer.clear_cache_type(cache_type, args.dry_run, args.limit)
                total += deleted
                logger.info("")

        # Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("")
        logger.info("=" * 60)
        logger.info("CACHE CLEARING OPERATION COMPLETED")
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Total Entries {'Would Be Deleted' if args.dry_run else 'Deleted'}: {total}")
        logger.info(f"Errors: {clearer.error_count}")
        logger.info("=" * 60)

        if clearer.error_count > 0:
            logger.warning(f"Completed with {clearer.error_count} errors")
            sys.exit(1)
        else:
            logger.info("✅ Operation completed successfully")
            sys.exit(0)

    except KeyboardInterrupt:
        logger.info("\n⚠️  Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Close Redis connection using project's standard cleanup
        logger.info("Closing Redis connection...")
        await close_redis()
        logger.info("Redis connection closed")


if __name__ == "__main__":
    asyncio.run(main())
