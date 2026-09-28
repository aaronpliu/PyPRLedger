"""Create release_check_baseline table and grant release_diff permissions

Revision ID: 033
Revises: 032
Create Date: 2026-09-28 00:00:00.000000

The per-build merge check compares a release against a baseline (the fork point of
a maintenance line, or the previous release of that line). Storing that baseline
per repository makes the routine reproducible for the whole team instead of living
in one engineer's browser.

The migration also adds the ``release_diff`` resource to the RBAC roles: every role
may read, while review_admin / system_admin may manage (that is, edit the stored
baseline).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "033"
down_revision: str | None = "032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


READ_ONLY_PERMISSIONS = ["read"]
MANAGE_PERMISSIONS = ["read", "manage"]


def _set_permissions(role: str, permissions: list[str]) -> None:
    """Give a role the release_diff actions (keeping its other permissions)."""
    actions = ", ".join(f"'{action}'" for action in permissions)
    op.execute(f"""
        UPDATE role
        SET permissions = JSON_SET(permissions, '$.release_diff', JSON_ARRAY({actions})),
            updated_at = NOW()
        WHERE name = '{role}'
    """)


def upgrade() -> None:
    """Create the baseline table and add release_diff permissions"""
    op.create_table(
        "release_check_baseline",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("git_provider", sa.String(length=32), nullable=False),
        sa.Column("project_key", sa.String(length=32), nullable=False),
        sa.Column("repository_slug", sa.String(length=128), nullable=False),
        sa.Column(
            "baseline_ref",
            sa.String(length=256),
            nullable=False,
            comment="Ref the missing check narrows against",
        ),
        sa.Column(
            "note",
            sa.String(length=255),
            nullable=True,
            comment="Why this baseline, e.g. 'fork point of the 1.x line'",
        ),
        sa.Column(
            "updated_by",
            sa.String(length=64),
            nullable=True,
            comment="Username of the last editor",
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_release_check_baseline_project",
        "release_check_baseline",
        ["project_key"],
    )
    op.create_index(
        "idx_release_check_baseline_slug",
        "release_check_baseline",
        ["repository_slug"],
    )
    op.create_index(
        "uk_release_check_baseline_repo",
        "release_check_baseline",
        ["git_provider", "project_key", "repository_slug"],
        unique=True,
    )

    for role in ("viewer", "reviewer"):
        _set_permissions(role, READ_ONLY_PERMISSIONS)
    for role in ("review_admin", "system_admin"):
        _set_permissions(role, MANAGE_PERMISSIONS)


def downgrade() -> None:
    """Drop the baseline table and the release_diff permissions"""
    for role in ("viewer", "reviewer", "review_admin", "system_admin"):
        op.execute(f"""
            UPDATE role
            SET permissions = JSON_REMOVE(permissions, '$.release_diff'),
                updated_at = NOW()
            WHERE name = '{role}'
        """)

    op.drop_index("uk_release_check_baseline_repo", table_name="release_check_baseline")
    op.drop_index("idx_release_check_baseline_slug", table_name="release_check_baseline")
    op.drop_index("idx_release_check_baseline_project", table_name="release_check_baseline")
    op.drop_table("release_check_baseline")
