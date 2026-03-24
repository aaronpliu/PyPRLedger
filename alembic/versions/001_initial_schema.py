"""Initial schema creation

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

This migration creates the complete initial schema with all enhancements:
- user table with business user_id (Integer)
- project table with business project_id (Integer)
- repository table with business repository_id (Integer) and FK to project.project_id
- pull_request_review table with:
  * Business key columns: project_key, repository_slug, reviewer, pull_request_user
  * Enhanced fields: reviewed_date, is_latest_review, review_iteration
  * Composite indexes for performance
  * No database ID foreign keys (project_id, repository_id, etc.)

All tables use business IDs (passed by API callers) for foreign key relationships,
not database auto-generated IDs.
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create complete initial database schema

    This consolidated migration includes all previous migrations:

    Phase 1: Base Tables (from original 001)
    1. user - User accounts with business user_id
    2. project - Projects with business project_id
    3. repository - Repositories linked to projects via business IDs

    Phase 2: Pull Request Review Table (consolidated from 001, 002, 003, 004)
    4. pull_request_review - Code reviews with:
       - Business key columns only (no database ID FKs)
       - Enhanced fields for multi-reviewer/multi-file support
       - Review iteration tracking
       - Comprehensive indexing

    Tables created:
    1. user - User accounts with business user_id
    2. project - Projects with business project_id
    3. repository - Repositories linked to projects via business IDs
    4. pull_request_review - Code reviews linked to all entities via business keys
    """

    # ============================================
    # 1. Create user table
    # ============================================
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),  # Business ID (e.g., GitHub user ID)
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("email_address", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_reviewer", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column(
            "created_date",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_date",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),  # Business ID must be unique
        sa.UniqueConstraint("email_address"),
    )

    # Create indexes for user table
    op.create_index(
        "idx_username", "user", ["username"], unique=True
    )  # Business ID index with unique constraint
    op.create_index("idx_email", "user", ["email_address"])

    # ============================================
    # 2. Create project table
    # ============================================
    op.create_table(
        "project",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "project_id", sa.Integer(), nullable=False
        ),  # Business ID (e.g., GitHub project ID)
        sa.Column("project_name", sa.String(length=128), nullable=False),
        sa.Column("project_key", sa.String(length=32), nullable=False),
        sa.Column("project_url", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "created_date",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_date",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),  # Business ID must be unique
        sa.UniqueConstraint("project_key"),
    )

    # Create indexes for project table
    op.create_index("idx_project_id", "project", ["project_id"])  # Business ID index

    # ============================================
    # 3. Create repository table
    # ============================================
    op.create_table(
        "repository",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "repository_id", sa.Integer(), nullable=False
        ),  # Business ID (e.g., GitHub repo ID)
        sa.Column(
            "project_id", sa.Integer(), nullable=False
        ),  # FK to project.project_id (business ID)
        sa.Column("repository_name", sa.String(length=128), nullable=False),
        sa.Column("repository_slug", sa.String(length=128), nullable=False),
        sa.Column("repository_url", sa.String(length=255), nullable=False),
        sa.Column(
            "created_date",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_date",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.project_id"], ondelete="CASCADE"
        ),  # FK to business ID
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id"),  # Business ID must be unique
    )

    # Create indexes for repository table
    op.create_index("idx_repository_id", "repository", ["repository_id"])  # Business ID index
    op.create_index("idx_repository_project_id", "repository", ["project_id"])  # FK index

    # ============================================
    # PHASE 2: Create pull_request_review table (consolidated version)
    # ============================================
    op.create_table(
        "pull_request_review",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # Business key columns (replacing database ID foreign keys)
        sa.Column("project_key", sa.String(length=32), nullable=False),
        sa.Column("repository_slug", sa.String(length=128), nullable=False),
        sa.Column("reviewer", sa.String(length=64), nullable=False),
        sa.Column("pull_request_user", sa.String(length=64), nullable=False),
        # Pull request information
        sa.Column("pull_request_id", sa.String(length=64), nullable=False),
        sa.Column("pull_request_commit_id", sa.String(length=64), nullable=True),
        sa.Column("source_branch", sa.String(length=64), nullable=False),
        sa.Column("target_branch", sa.String(length=64), nullable=False),
        # Code review details
        sa.Column("git_code_diff", sa.Text(), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("ai_suggestions", sa.JSON(), nullable=True),
        sa.Column("reviewer_comments", sa.Text(), nullable=True),
        # Review metrics
        sa.Column("score", sa.Integer(), nullable=True),
        # Status
        sa.Column("pull_request_status", sa.String(length=32), nullable=False),
        # Metadata
        sa.Column("metadata", sa.JSON(), nullable=True),
        # Enhanced fields for multi-reviewer/multi-file support
        sa.Column(
            "reviewed_date",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("is_latest_review", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("review_iteration", sa.Integer(), nullable=False, server_default="1"),
        # Timestamps
        sa.Column(
            "created_date",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_date",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
    )

    # ============================================
    # PHASE 3: Create comprehensive indexes
    # ============================================

    # Core business key indexes
    op.create_index("idx_pull_request_review_project_key", "pull_request_review", ["project_key"])
    op.create_index(
        "idx_pull_request_review_repository_slug", "pull_request_review", ["repository_slug"]
    )
    op.create_index("idx_pull_request_review_reviewer", "pull_request_review", ["reviewer"])
    op.create_index(
        "idx_pull_request_review_pull_request_user", "pull_request_review", ["pull_request_user"]
    )

    # Pull request identification
    op.create_index("idx_pull_request_id", "pull_request_review", ["pull_request_id"])

    # Enhanced query performance indexes
    op.create_index(
        "idx_unique_review_identifier",
        "pull_request_review",
        ["pull_request_commit_id", "project_key", "repository_slug", "source_filename", "reviewer"],
    )

    op.create_index("idx_reviewed_date", "pull_request_review", ["reviewed_date"])
    op.create_index("idx_is_latest_review", "pull_request_review", ["is_latest_review"])
    op.create_index("idx_created_date", "pull_request_review", ["created_date"])

    # Composite indexes for common query patterns
    op.create_index(
        "idx_pr_commit_project_repo",
        "pull_request_review",
        ["pull_request_commit_id", "project_key", "repository_slug"],
    )

    op.create_index("idx_reviewer_file", "pull_request_review", ["reviewer", "source_filename"])


def downgrade() -> None:
    """
    Drop all tables in reverse order of creation

    Order:
    1. Drop pull_request_review (has FKs to all other tables)
    2. Drop repository (has FK to project)
    3. Drop project
    4. Drop user
    """

    # Drop pull_request_review table and its indexes
    op.drop_index("idx_created_date", "pull_request_review")
    op.drop_index("idx_pr_project_id", "pull_request_review")
    op.drop_index("idx_reviewer_id", "pull_request_review")
    op.drop_index("idx_pull_request_id", "pull_request_review")
    op.drop_table("pull_request_review")

    # Drop repository table and its indexes
    op.drop_index("idx_repository_project_id", "repository")
    op.drop_index("idx_repository_id", "repository")
    op.drop_table("repository")

    # Drop project table and its indexes
    op.drop_index("idx_project_id", "project")
    op.drop_table("project")

    # Drop user table and its indexes
    op.drop_index("idx_email", "user")
    op.drop_index("idx_username", "user")
    op.drop_index("idx_user_id", "user")
    op.drop_table("user")
