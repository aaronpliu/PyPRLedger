"""Give an auto-registered repository the provider of its project

Revision ID: 035
Revises: 034
Create Date: 2026-10-13 00:00:00.000000

A repository first seen through a review registers itself, and that registration
left the provider to the column's own default - Bitbucket Server - whichever
provider the repository was actually on. The registry is where the release pages
resolve a repository's provider from, so those rows have to say what the project
says.

Only rows that disagree with their project are touched, and only where they sit on
that default - so a provider somebody chose for a repository, which is not the
default, is left exactly as it stands. A repository registered on the default while
its project is on another provider cannot be told apart from one that was never
given a provider at all, and it is aligned with its project; an administrator who
meant it can set it again on the registry page.
"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "035"
down_revision: str | None = "034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# What ``ProjectRegistry.git_provider`` defaults to, and therefore what an
# auto-registration was written with (``GitProvider.default()``).
DEFAULT_PROVIDER = "bitbucket_server"


def upgrade() -> None:
    """Align an auto-registered provider with the project of its repository."""
    op.execute(
        f"""
        UPDATE project_registry
        SET git_provider = (
            SELECT p.git_provider FROM project p
            WHERE p.project_key = project_registry.project_key
        )
        WHERE git_provider = '{DEFAULT_PROVIDER}'
          AND EXISTS (
            SELECT 1 FROM project p
            WHERE p.project_key = project_registry.project_key
              AND p.git_provider <> '{DEFAULT_PROVIDER}'
          )
        """
    )


def downgrade() -> None:
    """Left alone: which rows this aligned is not something to guess at."""
