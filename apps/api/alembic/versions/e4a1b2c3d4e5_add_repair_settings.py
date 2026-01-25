"""add repair settings

Revision ID: e4a1b2c3d4e5
Revises: 6b7a9a8b3c2d
Create Date: 2026-01-23 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e4a1b2c3d4e5"
down_revision: Union[str, None] = "6b7a9a8b3c2d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.add_column(
        "app_settings",
        sa.Column("repair_extract_metadata", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "app_settings",
        sa.Column("repair_delete_duplicates", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "app_settings",
        sa.Column("repair_update_manifests", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "app_settings",
        sa.Column("move_files_policy", sa.String(), nullable=False, server_default=sa.text("'report_only'")),
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_column("app_settings", "move_files_policy")
    op.drop_column("app_settings", "repair_update_manifests")
    op.drop_column("app_settings", "repair_delete_duplicates")
    op.drop_column("app_settings", "repair_extract_metadata")

