"""Add repository_id column to repository table

Revision ID: 005
Revises: 004
Create Date: 2026-03-22 00:23:17.000000

Note: This migration assumes that any existing 'repository_id_new' column 
has been manually removed from the database. It adds a new 'repository_id' 
column as Integer type for storing numeric repository identifiers.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Upgrade database schema:
    Add repository_id column to repository table as Integer type
    
    This column stores numeric repository identifiers (e.g., GitHub repo IDs)
    and is indexed for fast lookups.
    """
    
    # Check if repository_id column already exists
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt 
        FROM information_schema.COLUMNS 
        WHERE table_schema = DATABASE() 
        AND table_name = 'repository' 
        AND column_name = 'repository_id'
    """))
    
    column_exists = result.scalar() > 0
    
    # Only add column if it doesn't exist
    if not column_exists:
        # Add repository_id column as INTEGER
        op.add_column('repository', 
                      sa.Column('repository_id', sa.Integer(), nullable=True))
        
        # Populate existing records with a unique identifier
        # Use the auto-increment id as fallback if no external ID is available
        op.execute("""
            UPDATE repository 
            SET repository_id = id 
            WHERE repository_id IS NULL
        """)
        
        # Make repository_id NOT NULL after population
        op.alter_column('repository', 'repository_id',
                        existing_type=sa.Integer(),
                        nullable=False)
        
        # Create index on repository_id for faster lookups
        op.create_index('idx_repository_id', 'repository', ['repository_id'])
    else:
        print("Column 'repository_id' already exists, skipping creation")


def downgrade() -> None:
    """
    Downgrade database schema:
    Remove repository_id column from repository table
    
    Note: This will permanently delete the repository_id data.
    Make sure to backup data before downgrading.
    """
    
    # Check if repository_id column exists
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt 
        FROM information_schema.COLUMNS 
        WHERE table_schema = DATABASE() 
        AND table_name = 'repository' 
        AND column_name = 'repository_id'
    """))
    
    column_exists = result.scalar() > 0
    
    # Only drop column if it exists
    if column_exists:
        # Drop index first
        op.drop_index('idx_repository_id', 'repository')
        
        # Drop the column
        op.drop_column('repository', 'repository_id')
    else:
        print("Column 'repository_id' does not exist, skipping removal")
