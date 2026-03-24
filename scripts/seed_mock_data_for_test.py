"""
Seed script to insert mock data for testing multiple reviewers scenario

This script inserts:
- Project: ECOM (E-Commerce Platform)
- Repository: frontend-store
- Users: alice_dev, diana_reviewer, eve_senior
- PR Reviews: Multiple reviewers reviewing the same file

Run this before running test_multiple_reviewers.sh to avoid Bitbucket API calls.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, "src")


async def seed_mock_data():
    """Insert mock data for multi-reviewer test"""

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
            print("\n🌱 Seeding mock data for multi-reviewer test...\n")

            # 1. Create Project
            print("📁 Creating project: ECOM...")
            await session.execute(
                text("""
                INSERT INTO project (project_id, project_name, project_key, project_url, is_active, created_date, updated_date) 
                VALUES 
                (1, 'E-Commerce Platform', 'ECOM', 'https://bitbucket.org/company/ecom', TRUE, NOW(), NOW())
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
                (2, 'diana_reviewer', 'Diana Lee', 'diana.lee@example.com', TRUE, TRUE, NOW(), NOW()),
                (3, 'eve_senior', 'Eve Wilson', 'eve.wilson@example.com', TRUE, TRUE, NOW(), NOW())
            """)
            )
            print("✅ Created users: alice_dev, diana_reviewer, eve_senior")

            # Commit all inserts
            await session.commit()

            print("\n✅ Successfully seeded mock data!")
            print("\n📊 Summary:")
            print("  - 1 Project: ECOM")
            print("  - 1 Repository: frontend-store")
            print("  - 3 Users: alice_dev, diana_reviewer, eve_senior")
            print("\n🎯 Ready to run: bash scripts/test_multiple_reviewers.sh\n")

        except Exception as e:
            await session.rollback()
            if "Duplicate entry" in str(e):
                print("\n⚠️  Mock data already exists in database!")
                print("   You can run: python scripts/cleanup_database.py to reset")
                print("   Or proceed with the test directly.\n")
            else:
                print(f"\n❌ Error seeding data: {e}")
                import traceback

                traceback.print_exc()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_mock_data())
