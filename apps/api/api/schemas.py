from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

class PersonResponse(BaseModel):
    name: str
    asin: str | None = None

class ChapterResponse(BaseModel):
    index: int
    title: str
    start_offset_ms: int
    length_ms: int
    end_offset_ms: int

class SeriesResponse(BaseModel):
    name: str
    sequence: str | None = None

class TechnicalResponse(BaseModel):
    format: str | None = None
    bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    duration_ms: int | None = None
    file_size: int | None = None

class AssetResponse(BaseModel):
    asset_type: str
    path: str
    width: int | None = None
    height: int | None = None
    mime_type: str | None = None

class PlaybackProgressResponse(BaseModel):
    position_ms: int
    last_chapter_id: UUID | None = None
    playback_speed: float
    is_finished: bool
    last_played_at: datetime
    completed_at: datetime | None = None
    book_asin: str | None = None

class BookDetailsResponse(BaseModel):
    """Canonical response model for book details."""
    asin: str
    title: str
    subtitle: str | None = None
    description: str | None = None
    authors: list[PersonResponse] = []
    narrators: list[PersonResponse] = []
    series: SeriesResponse | None = None
    genres: list[str] = []
    publisher: str | None = None
    release_date: str | None = None
    language: str | None = None
    
    chapters: list[ChapterResponse] = []
    technical: TechnicalResponse | None = None
    assets: list[AssetResponse] = []
    playback_progress: PlaybackProgressResponse | None = None
    
    # Computed/Convenience fields
    cover_url: str | None = None
    duration_total_ms: int | None = None

class UpdateProgressRequest(BaseModel):
    position_ms: int
    playback_speed: float = 1.0
    is_finished: bool = False
    chapter_id: UUID | None = None
