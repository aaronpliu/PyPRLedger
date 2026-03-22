"""Add business key columns to pull_request_review table

Revision ID: 002
Revises: 001
Create Date: 2026-03-22 16:30:00.000000

This migration adds new columns to pull_request_review table to store business keys
directly instead of just database IDs. This enables automatic synchronization of
related entities when inserting or updating review records.

New columns added:
- project_key: References project.project_key (String)
- repository_slug: References repository.repository_slug (String)
- reviewer: References user.username (String)
- pull_request_user: References user.username (String)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add business key columns to pull_request_review table
    
    These columns allow direct relationship tracking using business keys
    instead of database auto-generated IDs.
    """
    
    # 1. Add project_key column (nullable initially for backfill)
    op.add_column(
        'pull_request_review',
        sa.Column('project_key', sa.String(length=32), nullable=True)
    )
    
    # 2. Add repository_slug column (nullable initially for backfill)
    op.add_column(
        'pull_request_review',
        sa.Column('repository_slug', sa.String(length=128), nullable=True)
    )
    
    # 3. Add reviewer column (nullable initially for backfill)
    op.add_column(
        'pull_request_review',
        sa.Column('reviewer', sa.String(length=64), nullable=True)
    )
    
    # 4. Add pull_request_user column (nullable initially for backfill)
    op.add_column(
        'pull_request_review',
        sa.Column('pull_request_user', sa.String(length=64), nullable=True)
    )
    
    # 5. Create indexes for better query performance
    op.create_index('idx_pull_request_review_project_key', 'pull_request_review', ['project_key'])
    op.create_index('idx_pull_request_review_repository_slug', 'pull_request_review', ['repository_slug'])
    op.create_index('idx_pull_request_review_reviewer', 'pull_request_review', ['reviewer'])
    op.create_index('idx_pull_request_review_pull_request_user', 'pull_request_review', ['pull_request_user'])
    
    # 6. Backfill existing records (set business keys from related tables)
    # Note: This populates the new columns with values from related tables
    op.execute("""
        UPDATE pull_request_review
        SET 
            project_key = (SELECT project_key FROM project WHERE project.project_id = pull_request_review.project_id),
            repository_slug = (SELECT repository_slug FROM repository WHERE repository.repository_id = pull_request_review.repository_id),
            reviewer = (SELECT username FROM user WHERE user.user_id = pull_request_review.reviewer_id),
            pull_request_user = (SELECT username FROM user WHERE user.user_id = pull_request_review.pull_request_user_id)
        WHERE project_key IS NULL
    """)
    
    # 7. Make columns NOT NULL after backfilling (MySQL requires type specification)
    op.alter_column('pull_request_review', 'project_key', 
                   existing_type=sa.String(length=32), nullable=False)
    op.alter_column('pull_request_review', 'repository_slug', 
                   existing_type=sa.String(length=128), nullable=False)
    op.alter_column('pull_request_review', 'reviewer', 
                   existing_type=sa.String(length=64), nullable=False)
    op.alter_column('pull_request_review', 'pull_request_user', 
                   existing_type=sa.String(length=64), nullable=False)


def downgrade() -> None:
    """
    Remove business key columns from pull_request_review table
    
    This reverts the changes made in the upgrade function.
    """
    # Drop indexes
    op.drop_index('idx_pull_request_review_pull_request_user', table_name='pull_request_review')
    op.drop_index('idx_pull_request_review_reviewer', table_name='pull_request_review')
    op.drop_index('idx_pull_request_review_repository_slug', table_name='pull_request_review')
    op.drop_index('idx_pull_request_review_project_key', table_name='pull_request_review')
    
    # Drop columns
    op.drop_column('pull_request_review', 'pull_request_user')
    op.drop_column('pull_request_review', 'reviewer')
    op.drop_column('pull_request_review', 'repository_slug')
    op.drop_column('pull_request_review', 'project_key')
