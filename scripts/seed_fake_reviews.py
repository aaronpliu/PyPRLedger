"""
Seed script to populate database with fake pull request review data

This script creates:
- Projects with business keys
- Repositories linked to projects
- Users (reviewers and PR authors)
- Pull requests with multiple files
- Reviews from multiple reviewers with iterations
"""

import asyncio
import sys
import os
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, 'src')


async def seed_data():
    """Insert fake data for testing multi-reviewer and multi-file reviews"""
    
    # Read database credentials from environment variables
    db_user = os.getenv('DATABASE_USER', 'root')
    db_password = os.getenv('DATABASE_PASSWORD', '')
    db_host = os.getenv('DATABASE_HOST', 'localhost')
    db_port = os.getenv('DATABASE_PORT', '3306')
    db_name = os.getenv('DATABASE_NAME', 'code_review')
    
    # Construct database URL
    database_url = f'mysql+aiomysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    
    print(f"🔧 Connecting to database: {db_user}@{db_host}:{db_port}/{db_name}")
    
    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            print("🌱 Seeding fake data...")
            
            # 1. Create Projects
            print("\n📁 Creating projects...")
            try:
                await session.execute(text("""
                    INSERT INTO project (project_id, project_name, project_key, project_url, created_date, updated_date) 
                    VALUES 
                    (1, 'E-Commerce Platform', 'ECOM', 'https://bitbucket.org/company/ecom', NOW(), NOW()),
                    (2, 'Analytics Dashboard', 'ANALYTICS', 'https://bitbucket.org/company/analytics', NOW(), NOW()),
                    (3, 'Mobile App Backend', 'MOBILE-API', 'https://bitbucket.org/company/mobile-api', NOW(), NOW())
                """))
                print("✅ Created 3 projects: ECOM, ANALYTICS, MOBILE-API")
            except Exception as e:
                if "Duplicate entry" in str(e):
                    print("ℹ️ Projects already exist, skipping...")
                else:
                    raise
            
            # Get the auto-generated IDs for projects
            result = await session.execute(text("SELECT project_id, project_key FROM project"))
            project_ids = {row[1]: row[0] for row in result}  # Map project_key to business ID (project_id)
            
            # 2. Create Repositories using correct project business IDs (project_id)
            print("\n🗂️ Creating repositories...")
            try:
                await session.execute(text(f"""
                    INSERT INTO repository (repository_id, project_id, repository_name, repository_slug, repository_url, created_date, updated_date) 
                    VALUES 
                    (1, {project_ids['ECOM']}, 'Frontend Store', 'frontend-store', 'https://bitbucket.org/company/ecom/frontend-store', NOW(), NOW()),
                    (2, {project_ids['ECOM']}, 'Payment Service', 'payment-service', 'https://bitbucket.org/company/ecom/payment-service', NOW(), NOW()),
                    (3, {project_ids['ANALYTICS']}, 'Dashboard UI', 'dashboard-ui', 'https://bitbucket.org/company/analytics/dashboard-ui', NOW(), NOW()),
                    (4, {project_ids['MOBILE-API']}, 'API Gateway', 'api-gateway', 'https://bitbucket.org/company/mobile-api/api-gateway', NOW(), NOW())
                """))
                print("✅ Created 4 repositories")
            except Exception as e:
                if "Duplicate entry" in str(e):
                    print("ℹ️ Repositories already exist, skipping...")
                else:
                    raise
            
            # 3. Create Users with business ID (user_id)
            print("\n👥 Creating users...")
            await session.execute(text("""
                INSERT INTO user (user_id, username, display_name, email_address, active, is_reviewer, created_date, updated_date) 
                VALUES 
                (1, 'alice_dev', 'Alice Johnson', 'alice.johnson@company.com', TRUE, FALSE, NOW(), NOW()),
                (2, 'bob_coder', 'Bob Smith', 'bob.smith@company.com', TRUE, FALSE, NOW(), NOW()),
                (3, 'charlie_ninja', 'Charlie Brown', 'charlie.brown@company.com', TRUE, FALSE, NOW(), NOW()),
                (4, 'diana_reviewer', 'Diana Lee', 'diana.lee@company.com', TRUE, TRUE, NOW(), NOW()),
                (5, 'eve_senior', 'Eve Wilson', 'eve.wilson@company.com', TRUE, TRUE, NOW(), NOW()),
                (6, 'frank_lead', 'Frank Miller', 'frank.miller@company.com', TRUE, TRUE, NOW(), NOW())
            """))
            print("✅ Created 6 users")
            
            # 4. Create Pull Request Reviews with multiple scenarios
            print("\n📝 Creating pull request reviews...")
            
            # Scenario 1: Multiple reviewers, single file, single iteration
            await session.execute(text("""
                INSERT INTO pull_request_review (
                    pull_request_id, pull_request_commit_id, project_key, repository_slug,
                    reviewer, pull_request_user, source_branch, target_branch,
                    git_code_diff, source_filename, ai_suggestions, reviewer_comments,
                    score, pull_request_status, metadata,
                    reviewed_date, is_latest_review, review_iteration,
                    created_date, updated_date
                ) VALUES (
                    'pr-001', 'abc123def456', 'ECOM', 'frontend-store',
                    'diana_reviewer', 'alice_dev', 'feature/shopping-cart', 'main',
                    'diff --git a/src/cart.py b/src/cart.py\n@@ -10,7 +10,9 @@\n+    def calculate_total(self):',
                    'src/services/cart.py',
                    '{"suggestion_1": "Add type hints", "suggestion_2": "Consider error handling"}',
                    'Good implementation overall. Consider adding more edge case tests.',
                    8, 'open', '{"labels": ["feature", "priority-high"]}',
                    NOW() - INTERVAL 2 DAY, TRUE, 1,
                    NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 2 DAY
                )
            """))
            
            # Scenario 2: Same reviewer, same file, second iteration (re-review)
            await session.execute(text("""
                INSERT INTO pull_request_review (
                    pull_request_id, pull_request_commit_id, project_key, repository_slug,
                    reviewer, pull_request_user, source_branch, target_branch,
                    git_code_diff, source_filename, ai_suggestions, reviewer_comments,
                    score, pull_request_status, metadata,
                    reviewed_date, is_latest_review, review_iteration,
                    created_date, updated_date
                ) VALUES (
                    'pr-001', 'abc123def456', 'ECOM', 'frontend-store',
                    'diana_reviewer', 'alice_dev', 'feature/shopping-cart', 'main',
                    'diff --git a/src/cart.py b/src/cart.py\n@@ -10,7 +10,12 @@\n+    def calculate_total(self):\n+        # Added error handling',
                    'src/services/cart.py',
                    '{"suggestion_1": "Great improvements!"}',
                    'Excellent revisions! The error handling looks much better now.',
                    9, 'open', '{"labels": ["feature", "priority-high"]}',
                    NOW() - INTERVAL 1 DAY, TRUE, 2,
                    NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 1 DAY
                )
            """))
            
            # Mark first iteration as not latest
            await session.execute(text("""
                UPDATE pull_request_review 
                SET is_latest_review = FALSE 
                WHERE pull_request_id = 'pr-001' 
                    AND project_key = 'ECOM' 
                    AND repository_slug = 'frontend-store'
                    AND source_filename = 'src/services/cart.py'
                    AND reviewer = 'diana_reviewer'
                    AND review_iteration = 1
            """))
            print("✅ Created PR-001: Multi-iteration review (cart.py)")
            
            # Scenario 3: Multiple reviewers on different files
            await session.execute(text("""
                INSERT INTO pull_request_review (
                    pull_request_id, pull_request_commit_id, project_key, repository_slug,
                    reviewer, pull_request_user, source_branch, target_branch,
                    git_code_diff, source_filename, ai_suggestions, reviewer_comments,
                    score, pull_request_status, metadata,
                    reviewed_date, is_latest_review, review_iteration,
                    created_date, updated_date
                ) VALUES (
                    'pr-002', 'def456ghi789', 'ECOM', 'payment-service',
                    'eve_senior', 'bob_coder', 'feature/stripe-integration', 'main',
                    'diff --git a/payments/stripe.py b/payments/stripe.py',
                    'payments/stripe.py',
                    '{"suggestion_1": "Use environment variables for API keys"}',
                    'Critical security concern: Never hardcode API keys!',
                    6, 'open', '{"security_review": true}',
                    NOW() - INTERVAL 3 DAY, TRUE, 1,
                    NOW() - INTERVAL 3 DAY, NOW() - INTERVAL 3 DAY
                ),
                (
                    'pr-002', 'def456ghi789', 'ECOM', 'payment-service',
                    'frank_lead', 'bob_coder', 'feature/stripe-integration', 'main',
                    'diff --git a/payments/stripe.py b/payments/stripe.py',
                    'payments/stripe.py',
                    '{"suggestion_1": "Add retry logic"}',
                    'Security issues must be fixed before merging.',
                    5, 'open', '{"security_review": true}',
                    NOW() - INTERVAL 3 DAY, TRUE, 1,
                    NOW() - INTERVAL 3 DAY, NOW() - INTERVAL 3 DAY
                )
            """))
            print("✅ Created PR-002: Multiple reviewers (stripe.py)")
            
            # Scenario 4: Overall PR review (no specific file)
            await session.execute(text("""
                INSERT INTO pull_request_review (
                    pull_request_id, pull_request_commit_id, project_key, repository_slug,
                    reviewer, pull_request_user, source_branch, target_branch,
                    git_code_diff, source_filename, ai_suggestions, reviewer_comments,
                    score, pull_request_status, metadata,
                    reviewed_date, is_latest_review, review_iteration,
                    created_date, updated_date
                ) VALUES (
                    'pr-002', 'def456ghi789', 'ECOM', 'payment-service',
                    'frank_lead', 'bob_coder', 'feature/stripe-integration', 'main',
                    NULL, NULL, NULL,
                    'Overall PR looks good architecture-wise. Just address the security concerns.',
                    7, 'open', '{"overall_review": true}',
                    NOW() - INTERVAL 2 DAY, TRUE, 1,
                    NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 2 DAY
                )
            """))
            print("✅ Created PR-002: Overall PR review (no file)")
            
            # Scenario 5: Multiple files in one PR, same reviewer
            await session.execute(text("""
                INSERT INTO pull_request_review (
                    pull_request_id, pull_request_commit_id, project_key, repository_slug,
                    reviewer, pull_request_user, source_branch, target_branch,
                    git_code_diff, source_filename, ai_suggestions, reviewer_comments,
                    score, pull_request_status, metadata,
                    reviewed_date, is_latest_review, review_iteration,
                    created_date, updated_date
                ) VALUES 
                (
                    'pr-003', 'ghi789jkl012', 'ANALYTICS', 'dashboard-ui',
                    'charlie_ninja', 'alice_dev', 'feature/charts', 'main',
                    'diff --git a/components/Chart.tsx b/components/Chart.tsx',
                    'src/components/Chart.tsx',
                    '{"suggestion_1": "Use React.memo for performance"}',
                    'Nice chart implementation! Consider optimizing re-renders.',
                    8, 'open', '{"file_type": "frontend"}',
                    NOW() - INTERVAL 1 DAY, TRUE, 1,
                    NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 1 DAY
                ),
                (
                    'pr-003', 'ghi789jkl012', 'ANALYTICS', 'dashboard-ui',
                    'charlie_ninja', 'alice_dev', 'feature/charts', 'main',
                    'diff --git a/utils/dataProcessor.ts b/utils/dataProcessor.ts',
                    'src/utils/dataProcessor.ts',
                    '{"suggestion_1": "Add input validation"}',
                    'Data processing logic is solid. Add more unit tests.',
                    7, 'open', '{"file_type": "utility"}',
                    NOW() - INTERVAL 1 DAY, TRUE, 1,
                    NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 1 DAY
                ),
                (
                    'pr-003', 'ghi789jkl012', 'ANALYTICS', 'dashboard-ui',
                    'charlie_ninja', 'alice_dev', 'feature/charts', 'main',
                    'diff --git a/styles/themes.css b/styles/themes.css',
                    'src/styles/themes.css',
                    '{"suggestion_1": "Use CSS variables"}',
                    'Clean CSS. Follow BEM naming convention.',
                    9, 'open', '{"file_type": "styles"}',
                    NOW() - INTERVAL 1 DAY, TRUE, 1,
                    NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 1 DAY
                )
            """))
            print("✅ Created PR-003: Multiple files reviewed by same reviewer")
            
            # Scenario 6: Complex scenario - multiple reviewers, multiple files, multiple iterations
            await session.execute(text("""
                INSERT INTO pull_request_review (
                    pull_request_id, pull_request_commit_id, project_key, repository_slug,
                    reviewer, pull_request_user, source_branch, target_branch,
                    git_code_diff, source_filename, ai_suggestions, reviewer_comments,
                    score, pull_request_status, metadata,
                    reviewed_date, is_latest_review, review_iteration,
                    created_date, updated_date
                ) VALUES 
                -- First reviewer, first file, first iteration
                (
                    'pr-004', 'jkl012mno345', 'MOBILE-API', 'api-gateway',
                    'eve_senior', 'charlie_ninja', 'feature/auth-middleware', 'main',
                    'diff --git a/middleware/auth.py b/middleware/auth.py',
                    'middleware/auth.py',
                    '{"suggestion_1": "Use JWT tokens"}',
                    'Authentication logic needs improvement.',
                    6, 'open', '{"security_critical": true}',
                    NOW() - INTERVAL 5 DAY, FALSE, 1,
                    NOW() - INTERVAL 5 DAY, NOW() - INTERVAL 5 DAY
                ),
                -- First reviewer, first file, second iteration
                (
                    'pr-004', 'jkl012mno345', 'MOBILE-API', 'api-gateway',
                    'eve_senior', 'charlie_ninja', 'feature/auth-middleware', 'main',
                    'diff --git a/middleware/auth.py b/middleware/auth.py',
                    'middleware/auth.py',
                    '{"suggestion_1": "JWT implementation looks good"}',
                    'Much better! JWT implementation is solid now.',
                    8, 'open', '{"security_critical": true}',
                    NOW() - INTERVAL 4 DAY, TRUE, 2,
                    NOW() - INTERVAL 4 DAY, NOW() - INTERVAL 4 DAY
                ),
                -- Second reviewer, same file, first iteration
                (
                    'pr-004', 'jkl012mno345', 'MOBILE-API', 'api-gateway',
                    'frank_lead', 'charlie_ninja', 'feature/auth-middleware', 'main',
                    'diff --git a/middleware/auth.py b/middleware/auth.py',
                    'middleware/auth.py',
                    '{"suggestion_1": "Add rate limiting"}',
                    'Good security improvements. Add rate limiting next.',
                    7, 'open', '{"security_critical": true}',
                    NOW() - INTERVAL 3 DAY, TRUE, 1,
                    NOW() - INTERVAL 3 DAY, NOW() - INTERVAL 3 DAY
                ),
                -- First reviewer, second file, first iteration
                (
                    'pr-004', 'jkl012mno345', 'MOBILE-API', 'api-gateway',
                    'eve_senior', 'charlie_ninja', 'feature/auth-middleware', 'main',
                    'diff --git a/routes/auth.py b/routes/auth.py',
                    'routes/auth.py',
                    '{"suggestion_1": "Validate request payloads"}',
                    'Route handlers look clean. Add input validation.',
                    7, 'open', '{"security_critical": true}',
                    NOW() - INTERVAL 3 DAY, TRUE, 1,
                    NOW() - INTERVAL 3 DAY, NOW() - INTERVAL 3 DAY
                )
            """))
            print("✅ Created PR-004: Complex scenario (multi-reviewer, multi-file, multi-iteration)")
            
            # Commit all inserts
            await session.commit()
            
            print("\n✅ Successfully seeded database!")
            print("\n📊 Summary:")
            print("  - 3 Projects: ECOM, ANALYTICS, MOBILE-API")
            print("  - 4 Repositories across projects")
            print("  - 6 Users (developers and reviewers)")
            print("  - 4 Pull Requests with various scenarios:")
            print("    * PR-001: Single file, 2 iterations by same reviewer")
            print("    * PR-002: 2 reviewers + overall PR review")
            print("    * PR-003: 3 files reviewed by same reviewer")
            print("    * PR-004: Complex - 2 reviewers, 2 files, multiple iterations")
            print(f"  - Total reviews created: {await get_review_count(session)}")
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error seeding data: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()


async def get_review_count(session):
    """Get total number of reviews"""
    result = await session.execute(text("SELECT COUNT(*) FROM pull_request_review"))
    return result.scalar()


if __name__ == "__main__":
    asyncio.run(seed_data())
