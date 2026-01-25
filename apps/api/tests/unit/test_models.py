"""Unit tests for database models."""

from datetime import datetime

import pytest
from sqlmodel import select

from db.models import (
    Book,
    BookCreate,
    BookStatus,
    BookUpdate,
    Job,
    JobStatus,
    JobType,
    SettingsModel,
    SettingsUpdate,
)


class TestBookModel:
    """Tests for Book model."""

    def test_book_creation_with_defaults(self) -> None:
        """Test creating a book with minimal required fields."""
        book = Book(asin="B00TEST", title="Test Book")

        assert book.asin == "B00TEST"
        assert book.title == "Test Book"
        assert book.status == BookStatus.NEW
        assert book.subtitle is None
        assert book.local_path_aax is None

    def test_book_status_transitions(self) -> None:
        """Test book status can be changed."""
        book = Book(asin="B00TEST", title="Test Book")

        assert book.status == BookStatus.NEW

        book.status = BookStatus.DOWNLOADING
        assert book.status == BookStatus.DOWNLOADING

        book.status = BookStatus.COMPLETED
        assert book.status == BookStatus.COMPLETED

    def test_book_with_all_fields(self, sample_book_data: dict) -> None:
        """Test creating a book with all fields."""
        book = Book(**sample_book_data)

        assert book.asin == "B00TEST123"
        assert book.title == "Test Audiobook"
        assert book.subtitle == "A Test Subtitle"
        assert book.runtime_length_min == 360

    def test_book_create_schema(self) -> None:
        """Test BookCreate schema validation."""
        book_create = BookCreate(
            asin="B00TEST",
            title="Test Book",
            runtime_length_min=120,
        )

        assert book_create.asin == "B00TEST"
        assert book_create.title == "Test Book"

    def test_book_update_schema_partial(self) -> None:
        """Test BookUpdate allows partial updates."""
        update = BookUpdate(status=BookStatus.DOWNLOADED)

        assert update.status == BookStatus.DOWNLOADED
        assert update.title is None
        assert update.local_path_aax is None

    def test_book_update_schema_full(self) -> None:
        """Test BookUpdate with multiple fields."""
        update = BookUpdate(
            status=BookStatus.COMPLETED,
            local_path_converted="/path/to/file.m4b",
            conversion_format="m4b",
        )

        assert update.status == BookStatus.COMPLETED
        assert update.local_path_converted == "/path/to/file.m4b"
        assert update.conversion_format == "m4b"


class TestJobModel:
    """Tests for Job model."""

    def test_job_creation_with_defaults(self) -> None:
        """Test creating a job with minimal fields."""
        job = Job(task_type=JobType.DOWNLOAD)

        assert job.task_type == JobType.DOWNLOAD
        assert job.status == JobStatus.PENDING
        assert job.progress_percent == 0
        assert job.id is not None

    def test_job_with_book_reference(self) -> None:
        """Test creating a job with book ASIN."""
        job = Job(
            task_type=JobType.CONVERT,
            book_asin="B00TEST123",
        )

        assert job.task_type == JobType.CONVERT
        assert job.book_asin == "B00TEST123"

    def test_job_status_values(self) -> None:
        """Test all job status values."""
        assert JobStatus.PENDING.value == "PENDING"
        assert JobStatus.QUEUED.value == "QUEUED"
        assert JobStatus.RUNNING.value == "RUNNING"
        assert JobStatus.COMPLETED.value == "COMPLETED"
        assert JobStatus.FAILED.value == "FAILED"
        assert JobStatus.CANCELLED.value == "CANCELLED"

    def test_job_type_values(self) -> None:
        """Test all job type values."""
        assert JobType.DOWNLOAD.value == "DOWNLOAD"
        assert JobType.CONVERT.value == "CONVERT"
        assert JobType.SYNC.value == "SYNC"

    def test_job_progress_bounds(self) -> None:
        """Test job progress percentage bounds."""
        job = Job(task_type=JobType.DOWNLOAD)

        job.progress_percent = 0
        assert job.progress_percent == 0

        job.progress_percent = 50
        assert job.progress_percent == 50

        job.progress_percent = 100
        assert job.progress_percent == 100

    def test_job_retry_tracking_defaults(self) -> None:
        """Test job retry tracking fields have correct defaults."""
        job = Job(task_type=JobType.CONVERT)

        assert job.attempt == 1
        assert job.original_job_id is None

    def test_job_retry_tracking_with_values(self) -> None:
        """Test job retry tracking fields can be set."""
        from uuid import uuid4

        original_id = uuid4()
        job = Job(
            task_type=JobType.CONVERT,
            book_asin="B00TEST123",
            attempt=2,
            original_job_id=original_id,
        )

        assert job.attempt == 2
        assert job.original_job_id == original_id


class TestSettingsModel:
    """Tests for Settings model."""

    def test_settings_defaults(self) -> None:
        """Test settings have correct defaults."""
        settings = SettingsModel()

        assert settings.output_format == "m4b"
        assert settings.single_file is True
        assert settings.compression_mp3 == 4
        assert settings.compression_flac == 5
        assert settings.compression_opus == 5
        assert settings.cover_size == "1215"
        assert settings.no_clobber is False
        assert settings.move_after_complete is False
        assert settings.auto_retry is True
        assert settings.max_retries == 3

    def test_settings_update_validation(self) -> None:
        """Test settings update validation."""
        # Valid MP3 compression
        update = SettingsUpdate(compression_mp3=5)
        assert update.compression_mp3 == 5

        # Valid FLAC compression
        update = SettingsUpdate(compression_flac=10)
        assert update.compression_flac == 10

    def test_settings_update_invalid_compression(self) -> None:
        """Test settings update rejects invalid compression values."""
        with pytest.raises(ValueError):
            SettingsUpdate(compression_mp3=10)  # Max is 9

        with pytest.raises(ValueError):
            SettingsUpdate(compression_flac=15)  # Max is 12

        with pytest.raises(ValueError):
            SettingsUpdate(compression_opus=11)  # Max is 10

    def test_settings_naming_schemes(self) -> None:
        """Test settings naming scheme fields."""
        settings = SettingsModel(
            dir_naming_scheme="$artist/$title",
            file_naming_scheme="$title - $narrator",
            chapter_naming_scheme="$chapter",
        )

        assert settings.dir_naming_scheme == "$artist/$title"
        assert settings.file_naming_scheme == "$title - $narrator"
        assert settings.chapter_naming_scheme == "$chapter"


class TestBookStatusEnum:
    """Tests for BookStatus enum."""

    def test_all_status_values_exist(self) -> None:
        """Test all expected status values exist."""
        expected_statuses = [
            "NEW",
            "DOWNLOADING",
            "DOWNLOADED",
            "VALIDATING",
            "VALIDATED",
            "CONVERTING",
            "COMPLETED",
            "FAILED",
        ]

        for status in expected_statuses:
            assert hasattr(BookStatus, status)

    def test_status_string_values(self) -> None:
        """Test status enum values are strings."""
        assert BookStatus.NEW.value == "NEW"
        assert BookStatus.COMPLETED.value == "COMPLETED"
        assert BookStatus.FAILED.value == "FAILED"
