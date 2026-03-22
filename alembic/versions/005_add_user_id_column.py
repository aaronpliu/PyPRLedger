"""Add user_id column to user table

Revision ID: 005
Revises: 004
Create Date: 2026-03-22 21:00:00.000000

This migration adds the missing user_id (business ID) column to the user table
to align with the User model definition.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add user_id column to user table
    
    This is a business ID field (separate from database primary key 'id')
    that will be used for integration with external systems.
    """
    # Check if column already exists before adding
    from sqlalchemy import text, inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Get existing columns
    columns = [col['name'] for col in inspector.get_columns('user')]
    
    if 'user_id' not in columns:
        # Add user_id column as nullable first to allow existing rows
        op.add_column(
            'user',
            sa.Column('user_id', sa.Integer(), nullable=True)
        )
        
        # Populate user_id with auto-incrementing values based on id
        # This ensures each existing user gets a unique business ID
        conn.execute(text("""
            UPDATE user 
            SET user_id = id + 1000 
            WHERE user_id IS NULL
        """))
        
        # Now make it NOT NULL and add unique constraint
        op.alter_column(
            'user',
            'user_id',
            existing_type=sa.Integer(),
            nullable=False
        )
        
        # Create unique index for business ID
        op.create_index('idx_user_id', 'user', ['user_id'], unique=True)
        
        print("✅ Added user_id column to user table")
    else:
        print("ℹ️ user_id column already exists, skipping")


def downgrade() -> None:
    """
    Remove user_id column from user table
    
    WARNING: This will permanently remove the business ID mapping.
    Make sure to backup data before downgrading.
    """
    from sqlalchemy import text, inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Get existing columns
    columns = [col['name'] for col in inspector.get_columns('user')]
    
    if 'user_id' in columns:
        # Drop the index first
        op.drop_index('idx_user_id', table_name='user')
        
        # Then drop the column
        op.drop_column('user', 'user_id')
        
        print("✅ Removed user_id column from user table")
    else:
        print("ℹ️ user_id column does not exist, skipping")
