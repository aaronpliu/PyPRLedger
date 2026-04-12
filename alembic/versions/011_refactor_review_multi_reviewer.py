"""Refactor review model to support multiple reviewers with base-assignment pattern

Revision ID: 011
Revises: 010
Create Date: 2026-04-12

This migration refactors the pull_request_review table into two tables:
1. pull_request_review_base - stores PR base information (once per PR+commit+file)
2. pull_request_review_assignment - stores reviewer assignments (one per reviewer)

Benefits:
- Eliminates data redundancy (git_code_diff, ai_suggestions stored once)
- Better supports multiple reviewers per PR
- Improved data consistency
- Easier to manage reviewer assignments
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = "011"
down_revision = "010"  # Adjust based on your latest migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema to support multi-reviewer architecture"""

    # Step 1: Create new base table
    op.create_table(
        "pull_request_review_base",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pull_request_id", sa.String(64), nullable=False, index=True),
        sa.Column("pull_request_commit_id", sa.String(64), nullable=True, index=True),
        sa.Column(
            "project_key",
            sa.String(32),
            sa.ForeignKey("project.project_key", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "repository_slug",
            sa.String(128),
            sa.ForeignKey("repository.repository_slug", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("source_filename", sa.String(255), nullable=True, index=True),
        # PR base information (stored once)
        sa.Column("source_branch", sa.String(64), nullable=False),
        sa.Column("target_branch", sa.String(64), nullable=False),
        sa.Column("git_code_diff", sa.Text(), nullable=True),
        sa.Column("ai_suggestions", mysql.JSON(), nullable=True),
        sa.Column("pull_request_status", sa.String(32), nullable=False),
        sa.Column("metadata", mysql.JSON(), nullable=True),
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
        # Unique constraint for PR + commit + file combination
        sa.UniqueConstraint(
            "pull_request_commit_id",
            "project_key",
            "repository_slug",
            "source_filename",
            name="uq_pr_commit_file",
        ),
    )

    # Step 2: Create assignment table
    op.create_table(
        "pull_request_review_assignment",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "review_base_id",
            sa.Integer(),
            sa.ForeignKey("pull_request_review_base.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "reviewer",
            sa.String(64),
            sa.ForeignKey("user.username", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Assignment tracking
        sa.Column(
            "assigned_by",
            sa.String(64),
            sa.ForeignKey("user.username", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("assigned_date", sa.DateTime(), nullable=True),
        sa.Column(
            "assignment_status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        # Reviewer-specific comments
        sa.Column("reviewer_comments", sa.Text(), nullable=True),
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
        # Unique constraint: one assignment per reviewer per base review
        sa.UniqueConstraint("review_base_id", "reviewer", name="uq_base_reviewer"),
    )

    # Step 3: Migrate existing data from pull_request_review to new tables
    # Extract unique base records (group by the unique constraint fields)
    op.execute(
        """
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
            source_filename,
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
        """
    )

    # Migrate assignments (including reviewer-specific data)
    op.execute(
        """
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
        """
    )

    # Step 4: Drop old indexes and constraints
    op.drop_index("idx_unique_review_identifier", table_name="pull_request_review")
    op.drop_index("idx_pr_commit_project_repo", table_name="pull_request_review")
    op.drop_index("idx_reviewer_file", table_name="pull_request_review")

    # Step 5: Rename old table for backup (don't delete immediately for safety)
    op.rename_table("pull_request_review", "pull_request_review_backup")

    # Step 6: Create view for backward compatibility (optional, can be removed later)
    op.execute(
        """
        CREATE VIEW pull_request_review AS
        SELECT 
            a.id as id,
            b.pull_request_id,
            b.pull_request_commit_id,
            b.project_key,
            b.repository_slug,
            b.source_filename,
            b.source_branch,
            b.target_branch,
            b.git_code_diff,
            b.ai_suggestions,
            b.pull_request_status,
            b.metadata,
            a.reviewer,
            a.assigned_by,
            a.assigned_date,
            a.assignment_status,
            a.reviewer_comments,
            b.created_date,
            b.updated_date
        FROM pull_request_review_base b
        LEFT JOIN pull_request_review_assignment a ON b.id = a.review_base_id
        """
    )

    # Step 7: Add indexes for performance
    op.create_index(
        "idx_assignment_by_reviewer",
        "pull_request_review_assignment",
        ["reviewer", "assignment_status"],
    )
    op.create_index(
        "idx_assignment_by_base",
        "pull_request_review_assignment",
        ["review_base_id"],
    )


def downgrade() -> None:
    """Downgrade database schema back to single table structure"""

    # Step 1: Drop view
    op.execute("DROP VIEW IF EXISTS pull_request_review")

    # Step 2: Restore old table from backup
    op.rename_table("pull_request_review_backup", "pull_request_review")

    # Step 3: Drop new tables
    op.drop_table("pull_request_review_assignment")
    op.drop_table("pull_request_review_base")
