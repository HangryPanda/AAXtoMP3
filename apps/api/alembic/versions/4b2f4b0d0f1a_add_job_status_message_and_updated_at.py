"""add_job_status_message_and_updated_at

Revision ID: 4b2f4b0d0f1a
Revises: d38dcf655434
Create Date: 2026-01-23 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4b2f4b0d0f1a"
down_revision: Union[str, None] = "d38dcf655434"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.add_column("jobs", sa.Column("status_message", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("result_json", sa.Text(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
    )
    op.execute("UPDATE jobs SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("jobs", "updated_at", nullable=False)


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_column("jobs", "updated_at")
    op.drop_column("jobs", "result_json")
    op.drop_column("jobs", "status_message")
