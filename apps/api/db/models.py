"""Database models using SQLModel."""

import ast
import json
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from pydantic import BaseModel, field_validator, model_validator
from sqlmodel import JSON, Column, Field, SQLModel


def _parse_jsonish_list(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        try:
            parsed = ast.literal_eval(raw)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []


def _parse_jsonish_dict(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        try:
            parsed = ast.literal_eval(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None


class BookStatus(str, Enum):
    """Book processing status."""

    NEW = "NEW"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    CONVERTING = "CONVERTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobType(str, Enum):
    """Job task type."""

    DOWNLOAD = "DOWNLOAD"
    CONVERT = "CONVERT"
    SYNC = "SYNC"
    REPAIR = "REPAIR"
    SCAN = "SCAN"


class JobStatus(str, Enum):
    """Job execution status."""

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AuthorSchema(BaseModel):
    """Schema for Author data."""
    asin: str | None = None
    name: str

class NarratorSchema(BaseModel):
    """Schema for Narrator data."""
    name: str

class SeriesSchema(BaseModel):
    """Schema for Series data."""
    asin: str | None = None
    title: str
    sequence: str | None = None

class ChapterSchema(BaseModel):
    """Schema for Chapter data extracted from media."""
    title: str
    length_ms: int
    start_offset_ms: int


class ProductImages(BaseModel):
    """Dynamic product images model with varying keys."""
    model_config = {"extra": "allow"}


class BookBase(SQLModel):
    """Base book model with common fields."""

    asin: str = Field(primary_key=True, index=True, description="Audible ASIN")
    title: str = Field(index=True, description="Book title")
    subtitle: str | None = Field(default=None, description="Book subtitle")
    authors_json: str = Field(default="[]", description="JSON array of author objects")
    narrators_json: str = Field(default="[]", description="JSON array of narrator objects")
    series_json: str | None = Field(default=None, description="JSON array of series objects")
    runtime_length_min: int = Field(default=0, description="Runtime in minutes")
    release_date: str | None = Field(default=None, description="Release date ISO string")
    purchase_date: str | None = Field(default=None, description="Purchase date ISO string")
    product_images_json: str | None = Field(default=None, description="JSON object of image URLs")
    publisher: str | None = Field(default=None, description="Publisher name")
    language: str | None = Field(default=None, description="Content language")
    format_type: str | None = Field(default=None, description="Audio format type")
    aax_available: bool = Field(default=False, description="AAX format available")
    aaxc_available: bool = Field(default=False, description="AAXC format available")


class Book(BookBase, table=True):
    """Book database table model."""

    __tablename__ = "books"

    status: BookStatus = Field(default=BookStatus.NEW, index=True)
    local_path_aax: str | None = Field(default=None, description="Local path to AAX/AAXC file")
    local_path_voucher: str | None = Field(default=None, description="Local path to voucher file")
    local_path_cover: str | None = Field(default=None, description="Local path to cover image")
    local_path_converted: str | None = Field(default=None, description="Local path to converted file")
    conversion_format: str | None = Field(default=None, description="Format of converted file")
    error_message: str | None = Field(default=None, description="Last error message")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata_json: Any | None = Field(
        default=None,
        sa_column=Column(JSON),
        description="Full raw Audible metadata blob",
    )


class BookCreate(BookBase):
    """Schema for creating a book."""

    pass


class BookUpdate(SQLModel):
    """Schema for updating a book."""

    title: str | None = None
    subtitle: str | None = None
    status: BookStatus | None = None
    local_path_aax: str | None = None
    local_path_voucher: str | None = None
    local_path_cover: str | None = None
    local_path_converted: str | None = None
    conversion_format: str | None = None
    error_message: str | None = None


class BookRead(BookBase):
    """Schema for reading a book, including parsed and enriched data."""

    status: BookStatus
    content_type: str | None = None
    local_path_aax: str | None
    local_path_voucher: str | None
    local_path_cover: str | None
    local_path_converted: str | None
    conversion_format: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    # Hidden field to source data from
    metadata_json: Any | None = Field(default=None, exclude=True)

    # Parsed fields using the renamed Schemas
    authors: list[AuthorSchema] = Field(default_factory=list)
    narrators: list[NarratorSchema] = Field(default_factory=list)
    series: list[SeriesSchema] | None = None
    product_images: dict[str, str] | None = None
    chapters: list[ChapterSchema] = Field(default_factory=list)

    # Exclude raw JSON fields from output, but keep them for internal use
    authors_json: str = Field(exclude=True)
    narrators_json: str = Field(exclude=True)
    series_json: str | None = Field(default=None, exclude=True)
    product_images_json: str | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def populate_parsed_fields(self) -> "BookRead":
        """
        Populate parsed fields from stored JSON-string columns.

        Using a model-level validator avoids relying on field-validation order and
        works reliably with SQLModel's from_attributes mode.
        """
        if not self.authors and self.authors_json:
            self.authors = [AuthorSchema.model_validate(a) for a in _parse_jsonish_list(self.authors_json)]

        if not self.narrators and self.narrators_json:
            self.narrators = [NarratorSchema.model_validate(n) for n in _parse_jsonish_list(self.narrators_json)]

        if self.series is None and self.series_json:
            series_list = _parse_jsonish_list(self.series_json)
            self.series = [SeriesSchema.model_validate(s) for s in series_list] if series_list else None

        if self.product_images is None and self.product_images_json:
            images = _parse_jsonish_dict(self.product_images_json)
            if images is not None:
                self.product_images = {str(k): str(v) for k, v in images.items() if v is not None}

        if self.content_type is None and self.metadata_json:
            mj = self.metadata_json
            if isinstance(mj, str):
                try:
                    mj = json.loads(mj)
                except Exception:
                    mj = None
            if isinstance(mj, dict):
                ct = mj.get("content_type") or mj.get("contentType")
                if isinstance(ct, str) and ct.strip():
                    self.content_type = ct.strip()

        return self

    @field_validator("chapters", mode="before")
    @classmethod
    def parse_chapters(cls, v: Any, info) -> Any:
        if v: return v
        data = info.data
        if "metadata_json" in data and data["metadata_json"]:
            mj = data["metadata_json"]
            # Handle both string (JSON) and dict (SQLAlchemy JSON type)
            if isinstance(mj, str):
                import json
                try:
                    mj = json.loads(mj)
                except:
                    return []
            if isinstance(mj, dict):
                return mj.get("chapters", [])
        return []


# --- New Metadata Tables ---

class Person(SQLModel, table=True):
    """Person entity (author or narrator)."""
    __tablename__ = "people"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)
    sort_name: str | None = Field(default=None)


class BookAuthor(SQLModel, table=True):
    """Link between Book and Person (Author)."""
    __tablename__ = "book_authors"

    book_asin: str = Field(foreign_key="books.asin", primary_key=True)
    person_id: UUID = Field(foreign_key="people.id", primary_key=True)
    role: str = Field(default="AUTHOR") # Could be used for other roles if needed
    ordinal: int = Field(default=0)


class BookNarrator(SQLModel, table=True):
    """Link between Book and Person (Narrator)."""
    __tablename__ = "book_narrators"

    book_asin: str = Field(foreign_key="books.asin", primary_key=True)
    person_id: UUID = Field(foreign_key="people.id", primary_key=True)
    ordinal: int = Field(default=0)


class Series(SQLModel, table=True):
    """Series entity."""
    __tablename__ = "series"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)


class BookSeries(SQLModel, table=True):
    """Link between Book and Series."""
    __tablename__ = "book_series"

    book_asin: str = Field(foreign_key="books.asin", primary_key=True)
    series_id: UUID = Field(foreign_key="series.id", primary_key=True)
    series_index: str | None = Field(default=None)


class Chapter(SQLModel, table=True):
    """Extracted chapter metadata."""
    __tablename__ = "chapters"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    book_asin: str = Field(foreign_key="books.asin", index=True)
    index: int
    title: str
    start_offset_ms: int # Aligned with ChapterSchema's start_offset_ms
    length_ms: int     # Aligned with ChapterSchema's length_ms
    end_offset_ms: int # Calculated from start_offset_ms + length_ms, useful for queries


class BookAsset(SQLModel, table=True):
    """Asset files associated with a book (e.g., cover art)."""
    __tablename__ = "book_assets"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    book_asin: str = Field(foreign_key="books.asin", index=True)
    asset_type: str = Field(index=True) # e.g., 'cover'
    path: str # Path to the asset file
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    hash: str | None = None # For fingerprinting


class BookTechnical(SQLModel, table=True):
    """Technical details extracted from the media file."""
    __tablename__ = "book_technical"

    book_asin: str = Field(foreign_key="books.asin", primary_key=True)
    format: str | None = None
    bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    duration_ms: int | None = None
    file_size: int | None = Field(default=None, sa_type=sa.BigInteger)
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    extractor_version: str | None = None


class PlaybackProgress(SQLModel, table=True):
    """User playback state."""
    __tablename__ = "playback_progress"

    book_asin: str = Field(foreign_key="books.asin", primary_key=True)
    position_ms: int = Field(default=0)
    last_chapter_id: UUID | None = Field(foreign_key="chapters.id", default=None)
    playback_speed: float = Field(default=1.0)
    is_finished: bool = Field(default=False)
    last_played_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class BookScanState(SQLModel, table=True):
    """State for managing file scans and invalidation."""
    __tablename__ = "book_scan_state"

    book_asin: str = Field(foreign_key="books.asin", primary_key=True) # Unique identifier for the book this scan state belongs to
    file_path: str = Field(index=True, unique=True) # The canonical path to the media file
    file_mtime: float # Last modification time of the file
    file_size: int = Field(sa_type=sa.BigInteger)    # Size of the file
    # Optional: A fast hash (e.g., first/last N MB) for stricter change detection
    fast_hash: str | None = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    extractor_version: str | None = Field(default=None) # Version of the metadata extractor used


class JobBase(SQLModel):
    """Base job model."""

    task_type: JobType = Field(description="Type of job task")
    book_asin: str | None = Field(default=None, foreign_key="books.asin", description="Related book ASIN")


class Job(JobBase, table=True):
    """Job database table model."""

    __tablename__ = "jobs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    status: JobStatus = Field(default=JobStatus.PENDING, index=True)
    progress_percent: int = Field(default=0, ge=0, le=100)
    status_message: str | None = Field(default=None, description="Latest human-readable status message")
    log_file_path: str | None = Field(default=None, description="Path to job log file")
    error_message: str | None = Field(default=None)
    result_json: str | None = Field(default=None, description="JSON result summary for UI/debugging")
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    payload_json: str | None = Field(default=None, description="JSON payload with job-specific config")
    # Retry tracking
    attempt: int = Field(default=1, description="Attempt number (1 = original, 2+ = retries)")
    original_job_id: UUID | None = Field(default=None, description="ID of the original job if this is a retry")


class JobCreate(JobBase):
    """Schema for creating a job."""

    payload: dict[str, Any] | None = None


class JobRead(JobBase):
    """Schema for reading a job."""

    id: UUID
    status: JobStatus
    progress_percent: int
    status_message: str | None
    log_file_path: str | None
    error_message: str | None
    result_json: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Retry tracking
    attempt: int = 1
    original_job_id: UUID | None = None


class LocalItem(SQLModel, table=True):
    """
    Locally available media that may not exist in the current Audible catalog.

    Used to keep a "Local Library" view stable over time (delisted books, etc.).
    """

    __tablename__ = "local_items"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    asin: str | None = Field(default=None, index=True, description="Best-effort identifier (may be non-Audible)")
    title: str = Field(default="Unknown", index=True)
    authors: str | None = Field(default=None, description="Display string, e.g. 'A, B'")
    output_path: str = Field(description="Container path to converted file (e.g. /converted/.../book.m4b)")
    cover_path: str | None = Field(default=None, description="Optional container path to cover image")
    format: str | None = Field(default=None, description="Output format, e.g. m4b")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LocalItemRead(SQLModel):
    id: UUID
    asin: str | None
    title: str
    authors: str | None
    output_path: str
    cover_path: str | None
    format: str | None
    created_at: datetime
    updated_at: datetime

class SettingsModel(SQLModel, table=True):
    """Application settings singleton table."""

    __tablename__ = "app_settings"

    id: int = Field(default=1, primary_key=True)  # Singleton pattern
    output_format: str = Field(default="m4b")
    single_file: bool = Field(default=True)
    compression_mp3: int = Field(default=4)
    compression_flac: int = Field(default=5)
    compression_opus: int = Field(default=5)
    cover_size: str = Field(default="1215")
    dir_naming_scheme: str = Field(default="$genre/$artist/$title")
    file_naming_scheme: str = Field(default="$title")
    chapter_naming_scheme: str = Field(default="")
    no_clobber: bool = Field(default=False)
    move_after_complete: bool = Field(default=False)
    auto_retry: bool = Field(default=True)
    max_retries: int = Field(default=3)
    author_override: str = Field(default="")
    keep_author_index: int = Field(default=0)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Add aaxtomp3_path to settings
    aaxtomp3_path: str = Field(default="/usr/local/bin/AAXtoMP3", description="Path to the AAXtoMP3 script")

    # Add cover_cache_dir to settings
    cover_cache_dir: str = Field(default="/app/data/covers", description="Directory to cache cover images")

    # Repair settings
    repair_extract_metadata: bool = Field(default=True, description="Extract metadata from M4B files during repair")
    repair_delete_duplicates: bool = Field(default=False, description="Auto-delete duplicate conversions during repair")
    repair_update_manifests: bool = Field(default=True, description="Update manifests from filesystem during repair")
    move_files_policy: str = Field(default="report_only", description="Policy for misplaced files: report_only, always_move, ask_each")


class SettingsUpdate(SQLModel):
    """Schema for updating settings."""

    output_format: str | None = None
    single_file: bool | None = None
    compression_mp3: int | None = None
    compression_flac: int | None = None
    compression_opus: int | None = None
    cover_size: str | None = None
    dir_naming_scheme: str | None = None
    file_naming_scheme: str | None = None
    chapter_naming_scheme: str | None = None
    no_clobber: bool | None = None
    move_after_complete: bool | None = None
    auto_retry: bool | None = None
    max_retries: int | None = None
    author_override: str | None = None
    keep_author_index: int | None = None
    aaxtomp3_path: str | None = None
    cover_cache_dir: str | None = None
    # Repair settings
    repair_extract_metadata: bool | None = None
    repair_delete_duplicates: bool | None = None
    repair_update_manifests: bool | None = None
    move_files_policy: str | None = None


    @field_validator("compression_mp3")
    @classmethod
    def validate_mp3_compression(cls, v: int | None) -> int | None:
        if v is not None and not 0 <= v <= 9:
            raise ValueError("MP3 compression must be between 0-9")
        return v

    @field_validator("compression_flac")
    @classmethod
    def validate_flac_compression(cls, v: int | None) -> int | None:
        if v is not None and not 0 <= v <= 12:
            raise ValueError("FLAC compression must be between 0-12")
        return v

    @field_validator("compression_opus")
    @classmethod
    def validate_opus_compression(cls, v: int | None) -> int | None:
        if v is not None and not 0 <= v <= 10:
            raise ValueError("Opus compression must be between 0-10")
        return v

    @field_validator("move_files_policy")
    @classmethod
    def validate_move_files_policy(cls, v: str | None) -> str | None:
        if v is not None and v not in ("report_only", "always_move", "ask_each"):
            raise ValueError("move_files_policy must be: report_only, always_move, or ask_each")
        return v
