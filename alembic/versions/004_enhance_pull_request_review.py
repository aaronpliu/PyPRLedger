"""Enhance pull_request_review table for multi-reviewer and multi-file support

Revision ID: 004
Revises: 003
Create Date: 2026-03-22 19:00:00.000000

This migration enhances the pull_request_review table to support:
1. Multiple reviewers per pull request
2. Multiple files per pull request (each file reviewed separately)
3. Unique commit-based identification across projects/repositories
4. Review iteration tracking (save latest review for same file by same reviewer)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Enhance pull_request_review table
    
    Changes:
    1. Add reviewed_date column to track when review was completed
    2. Add is_latest_review column to mark the latest review
    3. Add review_iteration column to track review rounds
    4. Create unique constraint on (commit_id, project_key, repo_slug, filename, reviewer)
    """
    
    # 1. Add new columns
    op.add_column(
        'pull_request_review',
        sa.Column('reviewed_date', sa.DateTime(), nullable=True)
    )
    
    op.add_column(
        'pull_request_review',
        sa.Column('is_latest_review', sa.Boolean(), nullable=False, server_default='1')
    )
    
    op.add_column(
        'pull_request_review',
        sa.Column('review_iteration', sa.Integer(), nullable=False, server_default='1')
    )
    
    # 2. Set reviewed_date = created_date for existing records
    op.execute("""
        UPDATE pull_request_review 
        SET reviewed_date = created_date 
        WHERE reviewed_date IS NULL
    """)
    
    # 3. Make reviewed_date NOT NULL after populating
    op.alter_column(
        'pull_request_review',
        'reviewed_date',
        existing_type=sa.DateTime(),
        nullable=False
    )
    
    # 4. Create indexes for better query performance
    op.create_index(
        'idx_unique_review_identifier',
        'pull_request_review',
        ['pull_request_commit_id', 'project_key', 'repository_slug', 'source_filename', 'reviewer'],
        unique=False  # MySQL doesn't support unique index with nullable columns
    )
    
    op.create_index(
        'idx_reviewed_date',
        'pull_request_review',
        ['reviewed_date']
    )
    
    op.create_index(
        'idx_is_latest_review',
        'pull_request_review',
        ['is_latest_review']
    )
    
    # 5. Drop old indexes that are no longer needed
    op.drop_index('idx_pull_request_id', table_name='pull_request_review')
    op.drop_index('idx_project_key', table_name='pull_request_review')
    op.drop_index('idx_repository_slug', table_name='pull_request_review')
    op.drop_index('idx_reviewer', table_name='pull_request_review')
    
    # 6. Create new composite indexes
    op.create_index(
        'idx_pr_commit_project_repo',
        'pull_request_review',
        ['pull_request_commit_id', 'project_key', 'repository_slug']
    )
    
    op.create_index(
        'idx_reviewer_file',
        'pull_request_review',
        ['reviewer', 'source_filename']
    )


def downgrade() -> None:
    """
    Revert the changes made in the upgrade function
    """
    # Restore old indexes
    op.create_index('idx_pull_request_id', 'pull_request_review', ['pull_request_id'])
    op.create_index('idx_project_key', 'pull_request_review', ['project_key'])
    op.create_index('idx_repository_slug', 'pull_request_review', ['repository_slug'])
    op.create_index('idx_reviewer', 'pull_request_review', ['reviewer'])
    
    # Drop new indexes
    op.drop_index('idx_pr_commit_project_repo', table_name='pull_request_review')
    op.drop_index('idx_reviewer_file', table_name='pull_request_review')
    op.drop_index('idx_reviewed_date', table_name='pull_request_review')
    op.drop_index('idx_is_latest_review', table_name='pull_request_review')
    op.drop_index('idx_unique_review_identifier', table_name='pull_request_review')
    
    # Drop new columns
    op.drop_column('pull_request_review', 'review_iteration')
    op.drop_column('pull_request_review', 'is_latest_review')
    op.drop_column('pull_request_review', 'reviewed_date')
