"""Add pull_request_commit_id to pull_request_review table

Revision ID: 003
Revises: 002
Create Date: 2026-03-21 23:54:59.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Upgrade database schema:
    Add pull_request_commit_id column to pull_request_review table
    """
    
    # Add pull_request_commit_id column
    op.add_column(
        'pull_request_review',
        sa.Column('pull_request_commit_id', sa.String(64), nullable=True)
    )
    
    # Create index on pull_request_commit_id for faster lookups
    op.create_index('idx_pull_request_commit_id', 'pull_request_review', ['pull_request_commit_id'])


def downgrade() -> None:
    """
    Downgrade database schema:
    Remove pull_request_commit_id column from pull_request_review table
    """
    
    # Drop index
    op.drop_index('idx_pull_request_commit_id', 'pull_request_review')
    
    # Drop column
    op.drop_column('pull_request_review', 'pull_request_commit_id')
