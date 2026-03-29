"""create_project_registry

Revision ID: 002
Revises: 001
Create Date: 2026-03-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create project_registry table
    op.create_table(
        "project_registry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("app_name", sa.String(length=64), nullable=False),
        sa.Column("project_key", sa.String(length=32), nullable=False),
        sa.Column("repository_slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_date", sa.DateTime(), nullable=False),
        sa.Column("updated_date", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_key"], ["project.project_key"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("ix_project_registry_app_name", "project_registry", ["app_name"])
    op.create_index("ix_project_registry_project_key", "project_registry", ["project_key"])
    op.create_index("ix_project_registry_repository_slug", "project_registry", ["repository_slug"])

    # Create unique constraint for (project_key, repository_slug)
    op.create_unique_constraint(
        "uk_project_repo_unique", "project_registry", ["project_key", "repository_slug"]
    )

    # Create composite index for efficient app-based queries
    op.create_index(
        "idx_app_project_repo", "project_registry", ["app_name", "project_key", "repository_slug"]
    )

    # Populate with existing projects - assign to 'Unknown' default app
    # This ensures backward compatibility
    op.execute("""
        INSERT INTO project_registry (app_name, project_key, repository_slug, description, created_date, updated_date)
        SELECT 
            'Unknown' as app_name,
            p.project_key,
            r.repository_slug,
            'Auto-registered during migration' as description,
            NOW() as created_date,
            NOW() as updated_date
        FROM project p
        JOIN repository r ON r.project_id = p.project_id
        WHERE NOT EXISTS (
            SELECT 1 FROM project_registry pr 
            WHERE pr.project_key = p.project_key AND pr.repository_slug = r.repository_slug
        )
    """)


def downgrade() -> None:
    # Drop indexes and constraints
    op.drop_index("idx_app_project_repo", table_name="project_registry")
    op.drop_constraint("uk_project_repo_unique", table_name="project_registry", type_="unique")
    op.drop_index("ix_project_registry_repository_slug", table_name="project_registry")
    op.drop_index("ix_project_registry_project_key", table_name="project_registry")
    op.drop_index("ix_project_registry_app_name", table_name="project_registry")

    # Drop table
    op.drop_table("project_registry")
