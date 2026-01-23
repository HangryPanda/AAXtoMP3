"""add_job_paused_status

Revision ID: 6b7a9a8b3c2d
Revises: 4b2f4b0d0f1a
Create Date: 2026-01-23 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6b7a9a8b3c2d"
down_revision: Union[str, None] = "4b2f4b0d0f1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'PAUSED'")


def downgrade() -> None:
    """Downgrade database schema."""
    # Postgres enum values cannot be removed easily.
    pass

