"""Add job retry tracking fields

Revision ID: f7a2b3c4d5e6
Revises: e4a1b2c3d4e5_add_repair_settings
Create Date: 2026-01-23

"""
from typing import Sequence, Union
from collections import defaultdict

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7a2b3c4d5e6'
down_revision: Union[str, None] = '9c1d3a4b5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add attempt column with default value of 1
    op.add_column('jobs', sa.Column('attempt', sa.Integer(), nullable=False, server_default='1'))
    # Add original_job_id column for linking retries
    op.add_column('jobs', sa.Column('original_job_id', sa.Uuid(), nullable=True))

    # Backfill: Set attempt numbers for existing jobs based on book_asin + task_type grouping
    # Jobs for the same book are considered retries if they have the same task_type
    connection = op.get_bind()

    # Get all jobs grouped by (book_asin, task_type), ordered by created_at
    result = connection.execute(
        sa.text("""
            SELECT id, book_asin, task_type, created_at
            FROM jobs
            WHERE book_asin IS NOT NULL
            ORDER BY book_asin, task_type, created_at ASC
        """)
    )

    # Group jobs by (book_asin, task_type)
    groups = defaultdict(list)
    for row in result:
        key = (row.book_asin, row.task_type)
        groups[key].append(row.id)

    # Update attempt numbers and original_job_id for each group
    for (book_asin, task_type), job_ids in groups.items():
        if len(job_ids) <= 1:
            continue  # Single job, no retries to track

        original_id = job_ids[0]  # First job is the original

        for attempt_num, job_id in enumerate(job_ids, start=1):
            if attempt_num == 1:
                # First job: attempt=1, no original_job_id
                continue

            # Subsequent jobs are retries
            connection.execute(
                sa.text("""
                    UPDATE jobs
                    SET attempt = :attempt, original_job_id = :original_id
                    WHERE id = :job_id
                """),
                {"attempt": attempt_num, "original_id": original_id, "job_id": job_id}
            )


def downgrade() -> None:
    op.drop_column('jobs', 'original_job_id')
    op.drop_column('jobs', 'attempt')
