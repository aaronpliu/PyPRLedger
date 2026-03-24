#!/usr/bin/env python3
"""
Database Cleanup Script

This script will completely wipe the database by dropping all tables.
Use this when you need to start fresh with a clean database.

Usage:
    python scripts/cleanup_database.py

Warning: This will DELETE ALL DATA permanently!
"""

import sys
from pathlib import Path


# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def cleanup_database():
    """
    Drop all tables in the database.

    Reads database credentials from environment variables or .env file.
    """
    # Load database URL from environment/config
    try:
        from src.core.config import settings

        database_url = settings.database_url
        print("🔧 Using database configuration from environment")
    except Exception as e:
        print(f"❌ Could not load DATABASE_URL from config: {e}")
        print("\nPlease ensure .env file exists or DATABASE_URL is set")
        return False

    # Replace async driver with sync driver for schema operations
    if "+aiomysql" in database_url:
        database_url = database_url.replace("+aiomysql", "+pymysql")

    # Mask password for display
    display_url = database_url.split("@")[-1] if "@" in database_url else database_url
    if "://" in database_url and "@" in database_url:
        creds_and_host = database_url.split("://")[1].split("@")[0]
        if ":" in creds_and_host:
            username = creds_and_host.split(":")[0]
            masked_creds = f"{username}:***"
            display_url = database_url.replace(creds_and_host, masked_creds)

    print(f"\n{'=' * 70}")
    print("⚠️  WARNING: DATABASE CLEANUP")
    print(f"{'=' * 70}")
    print(f"\nTarget database: {display_url}")
    print("\nThis operation will:")
    print("  ❌ Drop ALL tables")
    print("  ❌ Delete ALL data")
    print("  ❌ Reset Alembic migration history")
    print("\nThis action CANNOT be undone!")
    print(f"{'=' * 70}\n")

    # Ask for confirmation
    response = input("Are you sure you want to continue? Type 'YES' to confirm: ")
    if response.strip().upper() != "YES":
        print("\n❌ Cleanup cancelled by user")
        return False

    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(database_url)

        print("\n🗑️  Starting database cleanup...\n")

        with engine.connect() as conn:
            # Step 1: Disable foreign key checks
            print("Step 1: Disabling foreign key checks...")
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            conn.commit()
            print("  ✅ Foreign key checks disabled\n")

            # Step 2: Get all table names
            print("Step 2: Discovering tables...")
            result = conn.execute(
                text("""
                SELECT TABLE_NAME 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE()
                ORDER BY TABLE_NAME
            """)
            )
            tables = [row[0] for row in result]

            if not tables:
                print("  ℹ️  No tables found in database")
            else:
                print(f"  📋 Found {len(tables)} tables: {', '.join(tables)}\n")

            # Step 3: Drop tables in reverse dependency order
            print("Step 3: Dropping tables...")

            # Define drop order based on FK dependencies
            drop_order = [
                "pull_request_review",  # Depends on: project, user, repository
                "repository",  # Depends on: project
                "user",  # No dependencies
                "project",  # No dependencies
                "alembic_version",  # Migration tracking
            ]

            # Drop known tables first (in correct order)
            for table in drop_order:
                if table in tables:
                    try:
                        conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                        print(f"  ✅ Dropped table: {table}")
                        tables.remove(table)
                    except Exception as e:
                        print(f"  ⚠️  Error dropping {table}: {e}")

            # Drop any remaining tables (in case there are unknown tables)
            for table in tables:
                try:
                    conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                    print(f"  ✅ Dropped table: {table}")
                except Exception as e:
                    print(f"  ⚠️  Error dropping {table}: {e}")

            # Step 4: Re-enable foreign key checks
            print("\nStep 4: Re-enabling foreign key checks...")
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            conn.commit()
            print("  ✅ Foreign key checks re-enabled\n")

        print(f"{'=' * 70}")
        print("✅ DATABASE CLEANUP COMPLETED SUCCESSFULLY!")
        print(f"{'=' * 70}")
        print("\nNext steps:")
        print("  1. Run 'alembic upgrade head' to recreate all tables")
        print("  2. Run 'python scripts/seed_fake_reviews.py' to populate test data")
        print(f"{'=' * 70}\n")

        return True

    except Exception as e:
        print(f"\n❌ ERROR during cleanup: {e}")
        print("\nPlease check:")
        print("  - Database server is running")
        print("  - Database credentials are correct")
        print("  - You have sufficient privileges to drop tables")
        return False


def main():
    """Main entry point."""
    success = cleanup_database()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
