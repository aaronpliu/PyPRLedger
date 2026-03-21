"""Add repository_id as Integer type to pull_request_review table

Revision ID: 002
Revises: 001
Create Date: 2026-03-21 23:37:41.000000

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
    Upgrade database schema:
    1. Add pull_request_review.repository_id as INTEGER foreign key
    Note: repository.repository_id is already INTEGER in model (was changed from String)
    """
    
    # Add repository_id column to pull_request_review table
    op.add_column(
        'pull_request_review',
        sa.Column('repository_id', sa.Integer(), nullable=True)
    )
    
    # Set default value for existing records (use first repository or project's default)
    # This assumes each review belongs to a repository in the same project
    op.execute("""
        UPDATE pull_request_review 
        SET repository_id = (
            SELECT MIN(r.id) 
            FROM repository r 
            WHERE r.project_id = pull_request_review.project_id
        )
        WHERE repository_id IS NULL
    """)
    
    # Make repository_id NOT NULL (MySQL requires type specification)
    op.alter_column('pull_request_review', 'repository_id',
                    existing_type=sa.Integer(),
                    nullable=False,
                    type_=sa.Integer())
    
    # Create index on repository_id in pull_request_review table
    op.create_index('idx_repository_id', 'pull_request_review', ['repository_id'])
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_pull_request_review_repository',
        'pull_request_review',
        'repository',
        'repository_id',
        'id',
        ondelete='CASCADE'
    )


def downgrade() -> None:
    """
    Downgrade database schema:
    1. Remove pull_request_review.repository_id
    """
    
    # Drop foreign key constraint
    op.drop_constraint('fk_pull_request_review_repository', 'pull_request_review', type_='foreignkey')
    
    # Drop index on pull_request_review.repository_id
    op.drop_index('idx_repository_id', 'pull_request_review')
    
    # Drop repository_id column from pull_request_review
    op.drop_column('pull_request_review', 'repository_id')
