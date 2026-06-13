"""Change FK on review/score/assignment user references from CASCADE to SET NULL

This migration ensures reviews, assignments, and scores survive user deletion:
- pull_request_review_base.pull_request_user: ADD FK with SET NULL (currently no FK constraint at all)
- pull_request_review_assignment.reviewer: CHANGE FK from CASCADE to SET NULL
- pull_request_score.reviewer: CHANGE FK from CASCADE to SET NULL
All three columns are also changed from NOT NULL to NULL.

Revision ID: 026
Revises: 025
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === 0. Clean up orphaned references before adding FK constraints ===
    # Handle empty-string references (common in test/legacy data).
    op.execute(
        "UPDATE pull_request_review_base SET pull_request_user = NULL WHERE pull_request_user = ''"
    )
    op.execute("UPDATE pull_request_review_assignment SET reviewer = NULL WHERE reviewer = ''")
    op.execute("UPDATE pull_request_score SET reviewer = NULL WHERE reviewer = ''")
    # Set pull_request_user to NULL where the referenced user does not exist.
    op.execute(
        """UPDATE pull_request_review_base r
           LEFT JOIN user u ON r.pull_request_user = u.username
           SET r.pull_request_user = NULL
           WHERE u.username IS NULL"""
    )
    # Set reviewer to NULL in assignments where the referenced user does not exist.
    # (FK is dropped first, so we can update freely.)
    op.execute(
        """UPDATE pull_request_review_assignment a
           LEFT JOIN user u ON a.reviewer = u.username
           SET a.reviewer = NULL
           WHERE u.username IS NULL"""
    )
    # Set reviewer to NULL in scores where the referenced user does not exist.
    op.execute(
        """UPDATE pull_request_score s
           LEFT JOIN user u ON s.reviewer = u.username
           SET s.reviewer = NULL
           WHERE u.username IS NULL"""
    )

    # === 1. pull_request_review_base.pull_request_user ===
    # Column exists as VARCHAR(64) NOT NULL with an index but NO foreign key.
    # Alter to nullable and ADD the FK with SET NULL.
    op.alter_column(
        "pull_request_review_base",
        "pull_request_user",
        existing_type=sa.String(64),
        nullable=True,
        existing_nullable=True,
    )
    op.create_foreign_key(
        "fk_review_base_pull_request_user",
        source_table="pull_request_review_base",
        referent_table="user",
        local_cols=["pull_request_user"],
        remote_cols=["username"],
        ondelete="SET NULL",
    )

    # === 2. pull_request_review_assignment.reviewer ===
    # Column has FK pull_request_review_assignment_ibfk_2 with CASCADE.
    # Drop FK, alter to nullable, add FK with SET NULL.
    op.drop_constraint(
        "pull_request_review_assignment_ibfk_2",
        "pull_request_review_assignment",
        type_="foreignkey",
    )
    op.alter_column(
        "pull_request_review_assignment",
        "reviewer",
        existing_type=sa.String(64),
        nullable=True,
        existing_nullable=False,
    )
    op.create_foreign_key(
        "fk_assignment_reviewer",
        source_table="pull_request_review_assignment",
        referent_table="user",
        local_cols=["reviewer"],
        remote_cols=["username"],
        ondelete="SET NULL",
    )

    # === 3. pull_request_score.reviewer ===
    # Column has FK pull_request_score_ibfk_3 with CASCADE.
    # Drop FK, alter to nullable, add FK with SET NULL.
    op.drop_constraint(
        "pull_request_score_ibfk_3",
        "pull_request_score",
        type_="foreignkey",
    )
    op.alter_column(
        "pull_request_score",
        "reviewer",
        existing_type=sa.String(64),
        nullable=True,
        existing_nullable=False,
    )
    op.create_foreign_key(
        "fk_score_reviewer",
        source_table="pull_request_score",
        referent_table="user",
        local_cols=["reviewer"],
        remote_cols=["username"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # === 0. Restore non-null values before changing columns back to NOT NULL ===
    # Any NULL values were created by the upgrade (orphaned references).
    # Replace them with empty string as a neutral placeholder.
    op.execute(
        "UPDATE pull_request_review_base SET pull_request_user = '' WHERE pull_request_user IS NULL"
    )
    op.execute("UPDATE pull_request_review_assignment SET reviewer = '' WHERE reviewer IS NULL")
    op.execute("UPDATE pull_request_score SET reviewer = '' WHERE reviewer IS NULL")

    # === 1. pull_request_review_base.pull_request_user ===
    # Drop the SET NULL FK we added, restore NOT NULL. (Original had no FK at all.)
    op.drop_constraint(
        "fk_review_base_pull_request_user",
        "pull_request_review_base",
        type_="foreignkey",
    )
    op.alter_column(
        "pull_request_review_base",
        "pull_request_user",
        existing_type=sa.String(64),
        nullable=False,
        existing_nullable=True,
    )

    # === 2. pull_request_review_assignment.reviewer ===
    # Drop SET NULL FK, restore NOT NULL, add back CASCADE FK.
    op.drop_constraint(
        "fk_assignment_reviewer",
        "pull_request_review_assignment",
        type_="foreignkey",
    )
    op.alter_column(
        "pull_request_review_assignment",
        "reviewer",
        existing_type=sa.String(64),
        nullable=False,
        existing_nullable=True,
    )
    op.create_foreign_key(
        "pull_request_review_assignment_ibfk_2",
        source_table="pull_request_review_assignment",
        referent_table="user",
        local_cols=["reviewer"],
        remote_cols=["username"],
        ondelete="CASCADE",
    )

    # === 3. pull_request_score.reviewer ===
    # Drop SET NULL FK, restore NOT NULL, add back CASCADE FK.
    op.drop_constraint(
        "fk_score_reviewer",
        "pull_request_score",
        type_="foreignkey",
    )
    op.alter_column(
        "pull_request_score",
        "reviewer",
        existing_type=sa.String(64),
        nullable=False,
        existing_nullable=True,
    )
    op.create_foreign_key(
        "pull_request_score_ibfk_3",
        source_table="pull_request_score",
        referent_table="user",
        local_cols=["reviewer"],
        remote_cols=["username"],
        ondelete="CASCADE",
    )
