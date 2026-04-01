"""
Seed script to insert test data for POST /reviews endpoint testing

This script inserts:
- Project: ECOM (E-Commerce Platform)
- Repository: frontend-store
- Users: alice_dev (PR author), bob_reviewer, carol_senior (reviewers)
- Sample Pull Request Reviews with various scenarios

Run this before testing POST /reviews to avoid Bitbucket API calls.
"""

import asyncio
import json
import os
import sys
from datetime import UTC, datetime

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, "src")


async def seed_test_data():
    """Insert test data for review creation testing"""

    # Read database credentials from environment variables
    db_user = os.getenv("DATABASE_USER", "root")
    db_password = os.getenv("DATABASE_PASSWORD", "")
    db_host = os.getenv("DATABASE_HOST", "localhost")
    db_port = os.getenv("DATABASE_PORT", "3306")
    db_name = os.getenv("DATABASE_NAME", "code_review")

    # Construct database URL
    database_url = f"mysql+aiomysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    print(f"🔧 Connecting to database: {db_user}@{db_host}:{db_port}/{db_name}")

    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            print("\n🌱 Seeding test data for POST /reviews endpoint...\n")

            # 1. Create Project
            print("📁 Creating project: ECOM...")
            await session.execute(
                text("""
                INSERT INTO project (project_id, project_name, project_key, project_url, is_active, created_date, updated_date) 
                VALUES 
                (1, 'E-Commerce Platform', 'ECOM', 'https://bitbucket.org/company/ecom', TRUE, NOW(), NOW())
                ON DUPLICATE KEY UPDATE project_name=VALUES(project_name)
            """)
            )
            print("✅ Created project: ECOM")

            # 2. Create Repository
            print("\n🗂️ Creating repository: frontend-store...")
            await session.execute(
                text("""
                INSERT INTO repository (repository_id, project_id, repository_name, repository_slug, repository_url, created_date, updated_date) 
                VALUES 
                (1, 1, 'Frontend Store', 'frontend-store', 'https://bitbucket.org/company/ecom/frontend-store', NOW(), NOW())
                ON DUPLICATE KEY UPDATE repository_name=VALUES(repository_name)
            """)
            )
            print("✅ Created repository: frontend-store")

            # 3. Create Users
            print("\n👥 Creating users...")
            await session.execute(
                text("""
                INSERT INTO user (user_id, username, display_name, email_address, active, is_reviewer, created_date, updated_date) 
                VALUES 
                (1, 'alice_dev', 'Alice Johnson', 'alice.johnson@example.com', TRUE, FALSE, NOW(), NOW()),
                (2, 'bob_reviewer', 'Bob Smith', 'bob.smith@example.com', TRUE, TRUE, NOW(), NOW()),
                (3, 'carol_senior', 'Carol Williams', 'carol.williams@example.com', TRUE, TRUE, NOW(), NOW()),
                (4, 'dave_intern', 'David Brown', 'david.brown@example.com', TRUE, FALSE, NOW(), NOW())
                ON DUPLICATE KEY UPDATE username=VALUES(username)
            """)
            )
            print("✅ Created users: alice_dev, bob_reviewer, carol_senior, dave_intern")

            # 4. Create Sample PR Reviews
            print("\n📝 Creating sample pull request reviews...")

            # Review 1: File-level review with AI suggestions
            print("  - Creating review 1: File-level review with AI suggestions...")
            await session.execute(
                text("""
                INSERT INTO pull_request_review (
                    pull_request_id, pull_request_commit_id, project_key, repository_slug,
                    reviewer, pull_request_user, source_branch, target_branch,
                    git_code_diff, source_filename, ai_suggestions, reviewer_comments,
                    pull_request_status, metadata, created_date, updated_date
                ) VALUES (
                    'PR-001', 'abc123def', 'ECOM', 'frontend-store',
                    'bob_reviewer', 'alice_dev', 'feature/shopping-cart', 'main',
                    'diff --git a/src/components/Cart.js b/src/components/Cart.js\n@@ -10,7 +10,7 @@\n-  const total = items.reduce((sum, item) => sum + item.price, 0);\n+  const total = items.reduce((sum, item) => sum + (item.price * item.quantity), 0);',
                    'src/components/Cart.js',
                    '{"suggestions": [{"line": 13, "message": "Consider adding quantity calculation", "severity": "medium"}]}',
                    'Good implementation overall. Please consider edge cases for quantity updates.',
                    'open', '{"review_duration_seconds": 180, "lines_changed": 15}',
                    NOW(), NOW()
                )
            """)
            )

            # Review 2: PR-level review (no specific file)
            print("  - Creating review 2: PR-level review (overall assessment)...")
            await session.execute(
                text("""
                INSERT INTO pull_request_review (
                    pull_request_id, pull_request_commit_id, project_key, repository_slug,
                    reviewer, pull_request_user, source_branch, target_branch,
                    git_code_diff, source_filename, ai_suggestions, reviewer_comments,
                    pull_request_status, metadata, created_date, updated_date
                ) VALUES (
                    'PR-001', 'abc123def', 'ECOM', 'frontend-store',
                    'carol_senior', 'alice_dev', 'feature/shopping-cart', 'main',
                    NULL, NULL, NULL,
                    'Excellent work on the shopping cart feature! The code is clean and well-structured. Approved for merge.',
                    'open', '{"review_type": "comprehensive", "total_lines_reviewed": 250}',
                    NOW(), NOW()
                )
            """)
            )

            # Review 3: Another file review by same reviewer
            print("  - Creating review 3: Multiple files by same reviewer...")
            await session.execute(
                text("""
                INSERT INTO pull_request_review (
                    pull_request_id, pull_request_commit_id, project_key, repository_slug,
                    reviewer, pull_request_user, source_branch, target_branch,
                    git_code_diff, source_filename, ai_suggestions, reviewer_comments,
                    pull_request_status, metadata, created_date, updated_date
                ) VALUES (
                    'PR-001', 'abc123def', 'ECOM', 'frontend-store',
                    'bob_reviewer', 'alice_dev', 'feature/shopping-cart', 'main',
                    'diff --git a/src/services/cart.py b/src/services/cart.py\n@@ -25,6 +25,7 @@\n+    def apply_discount(self, code):\n+        if code not in self.valid_codes:\n+            raise InvalidDiscountCodeError()',
                    'src/services/cart.py',
                    '{"suggestions": [{"line": 28, "message": "Add validation for discount codes", "severity": "high"}]}',
                    'Please add unit tests for the discount logic.',
                    'open', '{"review_duration_seconds": 240, "lines_changed": 45}',
                    NOW(), NOW()
                )
            """)
            )

            # Review 4: Merged PR review
            print("  - Creating review 4: Merged PR review...")
            merge_date = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            await session.execute(
                text("""
                INSERT INTO pull_request_review (
                    pull_request_id, pull_request_commit_id, project_key, repository_slug,
                    reviewer, pull_request_user, source_branch, target_branch,
                    git_code_diff, source_filename, ai_suggestions, reviewer_comments,
                    pull_request_status, metadata, created_date, updated_date
                ) VALUES (
                    'PR-002', 'def456ghi', 'ECOM', 'frontend-store',
                    'carol_senior', 'dave_intern', 'fix/checkout-bug', 'main',
                    NULL, NULL, NULL,
                    'Great bug fix! The checkout flow works correctly now.',
                    'merged', :metadata_json,
                    NOW(), NOW()
                )
            """),
                {"metadata_json": json.dumps({"merge_date": merge_date})},
            )

            # Review 5: Draft PR review
            print("  - Creating review 5: Draft PR review...")
            await session.execute(
                text("""
                INSERT INTO pull_request_review (
                    pull_request_id, pull_request_commit_id, project_key, repository_slug,
                    reviewer, pull_request_user, source_branch, target_branch,
                    git_code_diff, source_filename, ai_suggestions, reviewer_comments,
                    pull_request_status, metadata, created_date, updated_date
                ) VALUES (
                    'PR-003', 'ghi789jkl', 'ECOM', 'frontend-store',
                    'bob_reviewer', 'alice_dev', 'wip/new-feature', 'main',
                    NULL, 'src/utils/helpers.js',
                    '{"suggestions": [{"line": 5, "message": "Consider using arrow functions", "severity": "low"}]}',
                    'This is still a work in progress. Please complete the implementation before final review.',
                    'draft', '{"is_early_review": true}',
                    NOW(), NOW()
                )
            """)
            )

            # Commit all inserts
            await session.commit()

            print("\n✅ Successfully seeded test data!")
            print("\n📊 Summary:")
            print("  - 1 Project: ECOM")
            print("  - 1 Repository: frontend-store")
            print("  - 4 Users:")
            print("    • alice_dev (PR author)")
            print("    • bob_reviewer (reviewer)")
            print("    • carol_senior (senior reviewer)")
            print("    • dave_intern (intern)")
            print("  - 5 Sample Reviews:")
            print("    • Review 1: File-level with AI suggestions")
            print("    • Review 2: PR-level overall assessment")
            print("    • Review 3: Multiple files by same reviewer")
            print("    • Review 4: Merged PR")
            print("    • Review 5: Draft PR")
            print("\n🎯 Test Scenarios Ready:")
            print("  ✓ File-level vs PR-level reviews")
            print("  ✓ Multiple reviewers per PR")
            print("  ✓ Multiple files per reviewer")
            print("  ✓ Different PR statuses (open, merged, draft)")
            print("  ✓ AI suggestions and metadata")
            print("\n🚀 You can now test POST /reviews endpoint!\n")

        except Exception as e:
            await session.rollback()
            if "Duplicate entry" in str(e):
                print("\n⚠️  Test data already exists in database!")
                print("   You can run: python scripts/cleanup_database.py to reset")
                print("   Or proceed with testing directly.\n")
            else:
                print(f"\n❌ Error seeding data: {e}")
                import traceback

                traceback.print_exc()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_test_data())
