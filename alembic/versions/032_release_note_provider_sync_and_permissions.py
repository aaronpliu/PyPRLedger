"""Link release notes to external git releases and grant release note permissions

Revision ID: 032
Revises: 031
Create Date: 2026-09-25 00:30:00.000000

A version release can now be pushed to the git provider (GitHub Enterprise
Releases) or imported from it, so the provider release id/url is stored on the
release itself.

The migration also adds the ``release_note`` resource to the RBAC roles:
every role may read releases, while review_admin / system_admin may manage them
(draft, publish, push, import, delete).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "032"
down_revision: str | None = "031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


READ_ONLY_PERMISSIONS = ["read"]
MANAGE_PERMISSIONS = ["read", "create", "update", "delete", "manage"]


def _set_permissions(role: str, permissions: list[str]) -> None:
    """Give a role the release_note actions (keeping its other permissions)."""
    actions = ", ".join(f"'{action}'" for action in permissions)
    op.execute(f"""
        UPDATE role
        SET permissions = JSON_SET(permissions, '$.release_note', JSON_ARRAY({actions})),
            updated_at = NOW()
        WHERE name = '{role}'
    """)


def upgrade() -> None:
    """Add provider release columns and release_note permissions"""

    op.add_column(
        "release_note",
        sa.Column(
            "external_provider",
            sa.String(length=32),
            nullable=True,
            comment="Git provider holding the published release (github_enterprise)",
        ),
    )
    op.add_column(
        "release_note",
        sa.Column(
            "external_id",
            sa.String(length=64),
            nullable=True,
            comment="Provider side release id",
        ),
    )
    op.add_column(
        "release_note",
        sa.Column(
            "external_url",
            sa.String(length=512),
            nullable=True,
            comment="Provider side release url",
        ),
    )

    for role in ("viewer", "reviewer"):
        _set_permissions(role, READ_ONLY_PERMISSIONS)
    for role in ("review_admin", "system_admin"):
        _set_permissions(role, MANAGE_PERMISSIONS)


def downgrade() -> None:
    """Drop the provider release columns and the release_note permissions"""

    for role in ("viewer", "reviewer", "review_admin", "system_admin"):
        op.execute(f"""
            UPDATE role
            SET permissions = JSON_REMOVE(permissions, '$.release_note'),
                updated_at = NOW()
            WHERE name = '{role}'
        """)

    op.drop_column("release_note", "external_url")
    op.drop_column("release_note", "external_id")
    op.drop_column("release_note", "external_provider")
