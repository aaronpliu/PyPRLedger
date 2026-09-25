"""Create release_note table

Revision ID: 031
Revises: 030
Create Date: 2026-09-25 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create release_note table"""
    op.create_table(
        "release_note",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_key", sa.String(length=32), nullable=False),
        sa.Column("repository_slug", sa.String(length=128), nullable=False),
        sa.Column(
            "tag_name",
            sa.String(length=255),
            nullable=False,
            comment="Git tag / version identifier",
        ),
        sa.Column("name", sa.String(length=255), nullable=False, comment="Release title"),
        sa.Column("body", sa.Text(), nullable=False, comment="Release notes (markdown)"),
        sa.Column(
            "previous_tag",
            sa.String(length=255),
            nullable=True,
            comment="Previous version used to generate the notes",
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="draft",
            comment="draft or published",
        ),
        sa.Column(
            "is_prerelease",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Pre-release flag",
        ),
        sa.Column("author", sa.String(length=64), nullable=True),
        sa.Column(
            "published_date",
            sa.DateTime(),
            nullable=True,
            comment="Set when the release is published",
        ),
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
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["project_key"], ["project.project_key"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_release_note_id", "release_note", ["id"])
    op.create_index("ix_release_note_project_key", "release_note", ["project_key"])
    op.create_index("ix_release_note_repository_slug", "release_note", ["repository_slug"])
    op.create_index(
        "uk_release_note_tag",
        "release_note",
        ["project_key", "repository_slug", "tag_name"],
        unique=True,
    )
    op.create_index(
        "idx_release_note_repo_status",
        "release_note",
        ["project_key", "repository_slug", "status", "published_date"],
    )


def downgrade() -> None:
    """Drop release_note table"""
    op.drop_index("idx_release_note_repo_status", table_name="release_note")
    op.drop_index("uk_release_note_tag", table_name="release_note")
    op.drop_index("ix_release_note_repository_slug", table_name="release_note")
    op.drop_index("ix_release_note_project_key", table_name="release_note")
    op.drop_index("ix_release_note_id", table_name="release_note")
    op.drop_table("release_note")
