"""Initial database schema with books, jobs, and settings tables.

Revision ID: 001_initial
Revises:
Create Date: 2024-01-21

This migration creates the initial database schema for the Audible Library Manager:
- books: Stores audiobook metadata and processing status
- jobs: Tracks download/conversion/sync tasks
- app_settings: Application configuration singleton
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    # ===========================================
    # Books table
    # ===========================================
    op.create_table(
        "books",
        sa.Column("asin", sa.String(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("subtitle", sa.String(), nullable=True),
        sa.Column("authors_json", sa.String(), nullable=False, server_default="[]"),
        sa.Column("narrators_json", sa.String(), nullable=False, server_default="[]"),
        sa.Column("series_json", sa.String(), nullable=True),
        sa.Column("runtime_length_min", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("release_date", sa.String(), nullable=True),
        sa.Column("purchase_date", sa.String(), nullable=True),
        sa.Column("product_images_json", sa.String(), nullable=True),
        sa.Column("publisher", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("format_type", sa.String(), nullable=True),
        sa.Column("aax_available", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("aaxc_available", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="NEW",
        ),
        sa.Column("local_path_aax", sa.String(), nullable=True),
        sa.Column("local_path_voucher", sa.String(), nullable=True),
        sa.Column("local_path_cover", sa.String(), nullable=True),
        sa.Column("local_path_converted", sa.String(), nullable=True),
        sa.Column("conversion_format", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )

    # Create indexes for books table
    op.create_index("ix_books_asin", "books", ["asin"], unique=True)
    op.create_index("ix_books_title", "books", ["title"], unique=False)
    op.create_index("ix_books_status", "books", ["status"], unique=False)
    op.create_index("ix_books_created_at", "books", ["created_at"], unique=False)
    op.create_index("ix_books_purchase_date", "books", ["purchase_date"], unique=False)

    # ===========================================
    # Jobs table
    # ===========================================
    op.create_table(
        "jobs",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("task_type", sa.String(), nullable=False),
        sa.Column("book_asin", sa.String(), sa.ForeignKey("books.asin", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("log_file_path", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("payload_json", sa.String(), nullable=True),
    )

    # Create indexes for jobs table
    op.create_index("ix_jobs_id", "jobs", ["id"], unique=True)
    op.create_index("ix_jobs_status", "jobs", ["status"], unique=False)
    op.create_index("ix_jobs_task_type", "jobs", ["task_type"], unique=False)
    op.create_index("ix_jobs_book_asin", "jobs", ["book_asin"], unique=False)
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"], unique=False)

    # ===========================================
    # App Settings table (singleton)
    # ===========================================
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("output_format", sa.String(), nullable=False, server_default="m4b"),
        sa.Column("single_file", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("compression_mp3", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("compression_flac", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("compression_opus", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("cover_size", sa.String(), nullable=False, server_default="1215"),
        sa.Column(
            "dir_naming_scheme",
            sa.String(),
            nullable=False,
            server_default="$genre/$artist/$title",
        ),
        sa.Column("file_naming_scheme", sa.String(), nullable=False, server_default="$title"),
        sa.Column("chapter_naming_scheme", sa.String(), nullable=False, server_default=""),
        sa.Column("no_clobber", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("move_after_complete", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("auto_retry", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("author_override", sa.String(), nullable=False, server_default=""),
        sa.Column("keep_author_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Ensure singleton pattern with check constraint
        sa.CheckConstraint("id = 1", name="app_settings_singleton_check"),
    )

    # Insert default settings row (singleton)
    op.execute(
        """
        INSERT INTO app_settings (id)
        VALUES (1)
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    """Drop all tables and indexes."""
    # Drop indexes first
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index("ix_jobs_book_asin", table_name="jobs")
    op.drop_index("ix_jobs_task_type", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_id", table_name="jobs")

    op.drop_index("ix_books_purchase_date", table_name="books")
    op.drop_index("ix_books_created_at", table_name="books")
    op.drop_index("ix_books_status", table_name="books")
    op.drop_index("ix_books_title", table_name="books")
    op.drop_index("ix_books_asin", table_name="books")

    # Drop tables
    op.drop_table("app_settings")
    op.drop_table("jobs")
    op.drop_table("books")
