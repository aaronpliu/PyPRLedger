"""Initial schema creation

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user table
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('display_name', sa.String(length=128), nullable=False),
        sa.Column('email_address', sa.String(length=255), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('is_reviewer', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_date', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email_address')
    )
    op.create_index('idx_username', 'user', ['username'])
    op.create_index('idx_email', 'user', ['email_address'])
    
    # Create project table
    op.create_table(
        'project',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('project_name', sa.String(length=128), nullable=False),
        sa.Column('project_key', sa.String(length=32), nullable=False),
        sa.Column('project_url', sa.String(length=255), nullable=False),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_date', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id'),
        sa.UniqueConstraint('project_key')
    )
    op.create_index('idx_project_id', 'project', ['project_id'])
    
    # Create repository table
    op.create_table(
        'repository',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('repository_id', sa.String(length=64), nullable=False),
        sa.Column('repository_name', sa.String(length=128), nullable=False),
        sa.Column('repository_slug', sa.String(length=128), nullable=False),
        sa.Column('repository_url', sa.String(length=255), nullable=False),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_date', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_repository_id', 'repository', ['repository_id'])
    op.create_index('idx_project_id', 'repository', ['project_id'])
    
    # Create pull_request_review table
    op.create_table(
        'pull_request_review',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pull_request_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('pull_request_user_id', sa.Integer(), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), nullable=False),
        sa.Column('source_branch', sa.String(length=64), nullable=False),
        sa.Column('target_branch', sa.String(length=64), nullable=False),
        sa.Column('git_code_diff', sa.Text(), nullable=True),
        sa.Column('source_filename', sa.String(length=255), nullable=True),
        sa.Column('ai_suggestions', sa.JSON(), nullable=True),
        sa.Column('reviewer_comments', sa.Text(), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('pull_request_status', sa.String(length=32), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_date', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pull_request_user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_pull_request_id', 'pull_request_review', ['pull_request_id'])
    op.create_index('idx_project_id', 'pull_request_review', ['project_id'])
    op.create_index('idx_reviewer_id', 'pull_request_review', ['reviewer_id'])
    op.create_index('idx_created_date', 'pull_request_review', ['created_date'])


def downgrade() -> None:
    op.drop_index('idx_created_date', 'pull_request_review')
    op.drop_index('idx_reviewer_id', 'pull_request_review')
    op.drop_index('idx_project_id', 'pull_request_review')
    op.drop_index('idx_pull_request_id', 'pull_request_review')
    op.drop_table('pull_request_review')
    
    op.drop_index('idx_project_id', 'repository')
    op.drop_index('idx_repository_id', 'repository')
    op.drop_table('repository')
    
    op.drop_index('idx_project_id', 'project')
    op.drop_table('project')
    
    op.drop_index('idx_email', 'user')
    op.drop_index('idx_username', 'user')
    op.drop_table('user')
