"""Bind users to repositories for project visibility.

Revision ID: 040
Revises: 039
Create Date: 2026-11-09

Project visibility is decided by explicit (subject, project_key, repository_slug)
grants rather than by role scope. Existing pull request authors are granted
their repositories here, so turning visibility on does not hide the projects
people already work on.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op


revision: str = "040"
down_revision: str | None = "039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCESS_TABLE = sa.table(
    "user_repository_access",
    sa.column("subject_type", sa.String(16)),
    sa.column("subject_id", sa.Integer()),
    sa.column("subject_username", sa.String(64)),
    sa.column("project_key", sa.String(32)),
    sa.column("repository_slug", sa.String(128)),
    sa.column("granted_by", sa.Integer()),
    sa.column("created_at", sa.DateTime()),
    sa.column("updated_at", sa.DateTime()),
)


def upgrade() -> None:
    op.create_table(
        "user_repository_access",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subject_type", sa.String(length=16), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("subject_username", sa.String(length=64), nullable=True),
        sa.Column("project_key", sa.String(length=32), nullable=False),
        sa.Column("repository_slug", sa.String(length=128), nullable=False),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subject_type",
            "subject_id",
            "project_key",
            "repository_slug",
            name="uq_user_repository_access",
        ),
    )
    op.create_index("ix_ura_subject", "user_repository_access", ["subject_type", "subject_id"])
    op.create_index("ix_ura_repo", "user_repository_access", ["project_key", "repository_slug"])
    op.create_index(
        op.f("ix_user_repository_access_id"), "user_repository_access", ["id"], unique=False
    )

    _backfill_existing_authors()


def _backfill_existing_authors() -> None:
    """Grant every existing PR author the repository the PR belongs to."""
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT DISTINCT b.project_key, b.repository_slug, u.id, u.username, a.id
            FROM pull_request_review_base b
            JOIN user u ON u.username = b.pull_request_user
            LEFT JOIN auth_user a ON a.user_id = u.id
            WHERE b.pull_request_user IS NOT NULL AND b.pull_request_user <> ''
            """
        )
    ).fetchall()

    now = datetime.now(UTC)
    seen: set[tuple[str, int, str, str]] = set()
    grants: list[dict] = []
    for project_key, repository_slug, git_user_id, username, auth_user_id in rows:
        candidates = (
            ("git_user", git_user_id),
            ("auth_user", auth_user_id),
        )
        for subject_type, subject_id in candidates:
            if subject_id is None:
                continue
            key = (subject_type, subject_id, project_key, repository_slug)
            if key in seen:
                continue
            seen.add(key)
            grants.append(
                {
                    "subject_type": subject_type,
                    "subject_id": subject_id,
                    "subject_username": username,
                    "project_key": project_key,
                    "repository_slug": repository_slug,
                    "granted_by": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )

    if grants:
        op.bulk_insert(ACCESS_TABLE, grants)


def downgrade() -> None:
    op.drop_table("user_repository_access")
