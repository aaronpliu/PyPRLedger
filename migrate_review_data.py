"""Manually migrate data from old pull_request_review table to new structure"""

import asyncio

from sqlalchemy import text

from src.core.database import get_db_context, init_db


async def migrate_data():
    """Migrate existing review data to new structure"""

    print("Starting data migration...")

    # Initialize database
    await init_db()

    async with get_db_context() as session:
        try:
            # Step 1: Insert base records (unique by commit+project+repo+file)
            print("\n1. Migrating base records...")
            await session.execute(
                text("""
                INSERT INTO pull_request_review_base (
                    pull_request_id,
                    pull_request_commit_id,
                    project_key,
                    repository_slug,
                    source_filename,
                    source_branch,
                    target_branch,
                    git_code_diff,
                    ai_suggestions,
                    pull_request_status,
                    metadata,
                    created_date,
                    updated_date
                )
                SELECT 
                    MIN(pull_request_id),
                    pull_request_commit_id,
                    project_key,
                    repository_slug,
                    MIN(source_filename),
                    MIN(source_branch),
                    MIN(target_branch),
                    MIN(git_code_diff),
                    MIN(ai_suggestions),
                    MIN(pull_request_status),
                    MIN(metadata),
                    MIN(created_date),
                    MAX(updated_date)
                FROM pull_request_review
                GROUP BY 
                    pull_request_commit_id,
                    project_key,
                    repository_slug,
                    COALESCE(source_filename, '')
            """)
            )
            await session.commit()

            # Count base records
            result = await session.execute(text("SELECT COUNT(*) FROM pull_request_review_base"))
            base_count = result.scalar()
            print(f"   ✅ Migrated {base_count} base records")

            # Step 2: Insert assignment records
            print("\n2. Migrating assignment records...")
            await session.execute(
                text("""
                INSERT INTO pull_request_review_assignment (
                    review_base_id,
                    reviewer,
                    assigned_by,
                    assigned_date,
                    assignment_status,
                    reviewer_comments,
                    created_date,
                    updated_date
                )
                SELECT 
                    base.id,
                    old.reviewer,
                    old.assigned_by,
                    old.assigned_date,
                    old.assignment_status,
                    old.reviewer_comments,
                    old.created_date,
                    old.updated_date
                FROM pull_request_review old
                INNER JOIN pull_request_review_base base ON
                    base.pull_request_commit_id = old.pull_request_commit_id AND
                    base.project_key = old.project_key AND
                    base.repository_slug = old.repository_slug AND
                    (base.source_filename = old.source_filename OR 
                     (base.source_filename IS NULL AND old.source_filename IS NULL))
                WHERE old.reviewer IS NOT NULL
            """)
            )
            await session.commit()

            # Count assignment records
            result = await session.execute(
                text("SELECT COUNT(*) FROM pull_request_review_assignment")
            )
            assign_count = result.scalar()
            print(f"   ✅ Migrated {assign_count} assignment records")

            print("\n✅ Data migration completed successfully!")
            return True

        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            import traceback

            traceback.print_exc()
            await session.rollback()
            return False


if __name__ == "__main__":
    success = asyncio.run(migrate_data())
    exit(0 if success else 1)
