"""Remove database ID columns from pull_request_review table

Revision ID: 003
Revises: 002
Create Date: 2026-03-22 17:30:00.000000

This migration removes the old database ID columns from pull_request_review table
since we now use business keys (project_key, repository_slug, reviewer, pull_request_user)
for all relationships.

Columns removed:
- project_id (Integer)
- repository_id (Integer)
- reviewer_id (Integer)
- pull_request_user_id (Integer)

Foreign keys and indexes for these columns are also dropped.
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
    Remove database ID columns from pull_request_review table
    
    These columns are no longer needed since we use business keys for relationships.
    """
    
    # 1. Drop foreign key constraints (if they exist)
    # Note: MySQL requires checking if constraint exists before dropping
    op.execute("""
        SET @fk_name = (
            SELECT CONSTRAINT_NAME 
            FROM information_schema.TABLE_CONSTRAINTS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'pull_request_review' 
            AND CONSTRAINT_NAME = 'fk_pull_request_review_project_id'
        )
    """)
    op.execute("""
        SET @sql = IF(@fk_name IS NOT NULL, 
                     CONCAT('ALTER TABLE pull_request_review DROP FOREIGN KEY ', @fk_name), 
                     'SELECT "Foreign key fk_pull_request_review_project_id does not exist"')
    """)
    op.execute("@sql")
    
    op.execute("""
        SET @fk_name = (
            SELECT CONSTRAINT_NAME 
            FROM information_schema.TABLE_CONSTRAINTS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'pull_request_review' 
            AND CONSTRAINT_NAME = 'fk_pull_request_review_repository_id'
        )
    """)
    op.execute("""
        SET @sql = IF(@fk_name IS NOT NULL, 
                     CONCAT('ALTER TABLE pull_request_review DROP FOREIGN KEY ', @fk_name), 
                     'SELECT "Foreign key fk_pull_request_review_repository_id does not exist"')
    """)
    op.execute("@sql")
    
    op.execute("""
        SET @fk_name = (
            SELECT CONSTRAINT_NAME 
            FROM information_schema.TABLE_CONSTRAINTS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'pull_request_review' 
            AND CONSTRAINT_NAME = 'fk_pull_request_review_reviewer_id'
        )
    """)
    op.execute("""
        SET @sql = IF(@fk_name IS NOT NULL, 
                     CONCAT('ALTER TABLE pull_request_review DROP FOREIGN KEY ', @fk_name), 
                     'SELECT "Foreign key fk_pull_request_review_reviewer_id does not exist"')
    """)
    op.execute("@sql")
    
    op.execute("""
        SET @fk_name = (
            SELECT CONSTRAINT_NAME 
            FROM information_schema.TABLE_CONSTRAINTS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'pull_request_review' 
            AND CONSTRAINT_NAME = 'fk_pull_request_review_pull_request_user_id'
        )
    """)
    op.execute("""
        SET @sql = IF(@fk_name IS NOT NULL, 
                     CONCAT('ALTER TABLE pull_request_review DROP FOREIGN KEY ', @fk_name), 
                     'SELECT "Foreign key fk_pull_request_review_pull_request_user_id does not exist"')
    """)
    op.execute("@sql")
    
    # 2. Drop indexes
    op.drop_index('idx_project_id', table_name='pull_request_review', if_exists=True)
    op.drop_index('idx_repository_id', table_name='pull_request_review', if_exists=True)
    op.drop_index('idx_reviewer_id', table_name='pull_request_review', if_exists=True)
    op.drop_index('idx_pull_request_user_id', table_name='pull_request_review', if_exists=True)
    
    # 3. Drop columns
    op.drop_column('pull_request_review', 'project_id')
    op.drop_column('pull_request_review', 'repository_id')
    op.drop_column('pull_request_review', 'reviewer_id')
    op.drop_column('pull_request_review', 'pull_request_user_id')


def downgrade() -> None:
    """
    Restore database ID columns to pull_request_review table
    
    This reverts the changes made in the upgrade function.
    Note: This is a destructive operation and data cannot be recovered.
    """
    # 1. Add columns back (nullable to allow existing rows)
    op.add_column(
        'pull_request_review',
        sa.Column('project_id', sa.Integer(), nullable=True)
    )
    op.add_column(
        'pull_request_review',
        sa.Column('repository_id', sa.Integer(), nullable=True)
    )
    op.add_column(
        'pull_request_review',
        sa.Column('reviewer_id', sa.Integer(), nullable=True)
    )
    op.add_column(
        'pull_request_review',
        sa.Column('pull_request_user_id', sa.Integer(), nullable=True)
    )
    
    # 2. Recreate indexes
    op.create_index('idx_project_id', 'pull_request_review', ['project_id'], unique=False)
    op.create_index('idx_repository_id', 'pull_request_review', ['repository_id'], unique=False)
    op.create_index('idx_reviewer_id', 'pull_request_review', ['reviewer_id'], unique=False)
    op.create_index('idx_pull_request_user_id', 'pull_request_review', ['pull_request_user_id'], unique=False)
    
    # 3. Recreate foreign keys
    op.create_foreign_key(
        'fk_pull_request_review_project_id',
        'pull_request_review',
        'project',
        'project_id',
        'project_id',
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'fk_pull_request_review_repository_id',
        'pull_request_review',
        'repository',
        'repository_id',
        'repository_id',
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'fk_pull_request_review_reviewer_id',
        'pull_request_review',
        'user',
        'reviewer_id',
        'user_id',
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'fk_pull_request_review_pull_request_user_id',
        'pull_request_review',
        'user',
        'pull_request_user_id',
        'user_id',
        ondelete='CASCADE'
    )
