import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID
import json
from collections.abc import Iterable
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import select, delete, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from db.models import (
    Book, BookRead, BookStatus, Job, JobType, JobStatus,
    Person, Series, BookAuthor, BookNarrator, BookSeries, Chapter,
    BookAsset, BookTechnical, PlaybackProgress, SettingsModel
)
from api.schemas import (
    BookDetailsResponse, ChapterResponse, TechnicalResponse,
    AssetResponse, PlaybackProgressResponse, UpdateProgressRequest,
    PersonResponse, SeriesResponse
)
from services.library_manager import LibraryManager
from services.metadata_extractor import MetadataExtractor

router = APIRouter(tags=["library"])
logger = logging.getLogger(__name__)


class RepairPreviewResponse(BaseModel):
    """Response for repair preview with filesystem and database stats."""

    remote_total: int
    downloaded_total: int
    converted_total: int
    converted_of_downloaded: int
    orphan_downloads: int
    orphan_conversions: int
    missing_files: int
    duplicate_conversions: int
    # Disk-derived metrics
    downloaded_on_disk_total: int
    downloaded_on_disk_remote_total: int
    converted_m4b_files_on_disk_total: int
    converted_m4b_titles_on_disk_total: int
    converted_m4b_in_audiobook_dir_total: int
    converted_m4b_outside_audiobook_dir_total: int
    # Database-derived metrics
    downloaded_db_total: int
    converted_db_total: int
    misplaced_files_count: int
    generated_at: datetime


class RepairApplyResponse(BaseModel):
    """Response for repair apply."""

    job_id: str
    status: Literal["queued"]
    message: str

# Re-use instances where possible, though in a real app these might be dependencies
metadata_extractor = MetadataExtractor()
library_manager = LibraryManager(metadata_extractor)

@router.get("/debug/raw")
async def debug_raw_library(session: AsyncSession = Depends(get_session)):
    """Debug endpoint to see raw books in DB."""
    result = await session.execute(select(Book))
    books = result.scalars().all()
    return [{"asin": b.asin, "title": b.title, "status": b.status} for b in books]

@router.get("/{asin}/raw")
async def get_book_raw(asin: str, session: AsyncSession = Depends(get_session)):
    """Debug endpoint to see raw book record."""
    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book.dict()

@router.get("/sync/status")
async def get_sync_status(session: AsyncSession = Depends(get_session)):
    """Get status of the latest sync job."""
    result = await session.execute(
        select(Job)
        .where(Job.task_type == JobType.SYNC)
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        return {"status": "idle"}
        
    return {
        "status": "running" if job.status in [JobStatus.PENDING, JobStatus.RUNNING] else "idle",
        "last_sync": job.completed_at,
        "error": job.error_message if job.status == JobStatus.FAILED else None,
        "progress": job.progress_percent
    }

@router.get("/series")
async def list_series(
    session: AsyncSession = Depends(get_session),
    q: str | None = None
):
    """List all series, optionally filtered by name."""
    statement = select(Series)
    if q:
        statement = statement.where(Series.name.ilike(f"%{q}%"))
    statement = statement.order_by(Series.name)
    
    result = await session.execute(statement)
    return result.scalars().all()

@router.get("/repair/preview", response_model=RepairPreviewResponse)
async def repair_preview(
    session: AsyncSession = Depends(get_session),
) -> RepairPreviewResponse:
    """Preview repair metrics based on manifests + filesystem without mutating the DB."""
    from services.repair_pipeline import compute_preview

    try:
        preview = await compute_preview(session)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("Error computing repair preview")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return RepairPreviewResponse(
        remote_total=preview.remote_total,
        downloaded_total=preview.downloaded_total,
        converted_total=preview.converted_total,
        converted_of_downloaded=preview.converted_of_downloaded,
        orphan_downloads=preview.orphan_downloads,
        orphan_conversions=preview.orphan_conversions,
        missing_files=preview.missing_files,
        duplicate_conversions=preview.duplicate_conversions,
        downloaded_on_disk_total=preview.downloaded_on_disk_total,
        downloaded_on_disk_remote_total=preview.downloaded_on_disk_remote_total,
        converted_m4b_files_on_disk_total=preview.converted_m4b_files_on_disk_total,
        converted_m4b_titles_on_disk_total=preview.converted_m4b_titles_on_disk_total,
        converted_m4b_in_audiobook_dir_total=preview.converted_m4b_in_audiobook_dir_total,
        converted_m4b_outside_audiobook_dir_total=preview.converted_m4b_outside_audiobook_dir_total,
        downloaded_db_total=preview.downloaded_db_total,
        converted_db_total=preview.converted_db_total,
        misplaced_files_count=preview.misplaced_files_count,
        generated_at=datetime.now(UTC),
    )


@router.post("/repair/apply", response_model=RepairApplyResponse, status_code=202)
async def repair_apply(
    session: AsyncSession = Depends(get_session),
) -> RepairApplyResponse:
    """Queue a repair job that reconciles DB with manifests + filesystem."""
    from api.routes.jobs import job_manager

    job = Job(task_type=JobType.REPAIR, status=JobStatus.PENDING, progress_percent=0)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    await job_manager.queue_repair(job.id)

    return RepairApplyResponse(
        job_id=str(job.id),
        status="queued",
        message="Repair job queued. Check /jobs for progress.",
    )

@router.get("/repair/dry-run/{asin}")
async def repair_dry_run(asin: str, session: AsyncSession = Depends(get_session)):
    """See what metadata would be extracted for a single book."""
    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()
    if not book or not book.local_path_converted:
        raise HTTPException(status_code=404, detail="Book or converted file not found")
        
    metadata = await metadata_extractor.extract(book.local_path_converted)
    return metadata.dict()

@router.get("")
async def get_books(
    session: AsyncSession = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
    q: str | None = None,
    author: str | None = None,
    series: str | None = None,
    status: BookStatus | None = None,
    sort_by: Literal["title", "author", "release_date", "purchase_date", "runtime", "created_at"] = "title",
    sort_dir: Literal["asc", "desc"] = "asc"
):
    """List books with filtering, search, and pagination."""
    statement = select(Book)
    
    # 1. Filters
    if q:
        statement = statement.where(
            or_(
                Book.title.ilike(f"%{q}%"),
                Book.subtitle.ilike(f"%{q}%"),
                Book.authors_json.ilike(f"%{q}%")
            )
        )
    if author:
        statement = statement.where(Book.authors_json.ilike(f"%{author}%"))
    if status:
        statement = statement.where(Book.status == status)
    if series:
        statement = statement.where(Book.series_json.ilike(f"%{series}%"))

    # 2. Total Count (before pagination)
    count_statement = select(func.count()).select_from(statement.subquery())
    total_result = await session.execute(count_statement)
    total = total_result.scalar() or 0

    # 3. Sorting
    order_col = getattr(Book, sort_by if sort_by != "runtime" else "runtime_length_min")
    if sort_dir == "desc":
        statement = statement.order_by(order_col.desc())
    else:
        statement = statement.order_by(order_col.asc())

    # 4. Pagination
    statement = statement.offset(skip).limit(limit)
    
    result = await session.execute(statement)
    books = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [BookRead.model_validate(book) for book in books]
    }

@router.get("/local")
async def get_local_items(
    session: AsyncSession = Depends(get_session),
    skip: int = 0,
    limit: int = 100
):
    """List standalone local audiobooks (not from Audible)."""
    from db.models import LocalItem
    result = await session.execute(select(LocalItem).offset(skip).limit(limit))
    return result.scalars().all()

@router.get("/local/{local_id}")
async def get_local_item(
    local_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Get details for a standalone local audiobook."""
    from db.models import LocalItem
    result = await session.execute(select(LocalItem).where(LocalItem.id == local_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.get("/continue-listening", response_model=list[PlaybackProgressResponse])
async def continue_listening(
    session: AsyncSession = Depends(get_session),
    limit: int = 5
) -> list[PlaybackProgressResponse]:
    """Get books in progress, sorted by last played."""
    result = await session.execute(
        select(PlaybackProgress)
        .where(PlaybackProgress.is_finished == False)
        .order_by(PlaybackProgress.last_played_at.desc())
        .limit(limit)
    )
    progress_rows = result.scalars().all()

    responses = []
    for p in progress_rows:
        responses.append(PlaybackProgressResponse(
            position_ms=p.position_ms,
            last_chapter_id=p.last_chapter_id,
            playback_speed=p.playback_speed,
            is_finished=p.is_finished,
            last_played_at=p.last_played_at,
            completed_at=p.completed_at,
            book_asin=p.book_asin
        ))
    return responses

@router.get("/{asin}")
async def get_book(asin: str, session: AsyncSession = Depends(get_session)):
    """Get a single book by ASIN."""
    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return BookRead.model_validate(book)

@router.patch("/{asin}")
async def update_book(
    asin: str,
    updates: dict[str, Any],
    session: AsyncSession = Depends(get_session)
):
    """Update book fields manually."""
    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
        
    for key, value in updates.items():
        if hasattr(book, key):
            setattr(book, key, value)
            
    await session.commit()
    await session.refresh(book)
    return book

@router.delete("/{asin}")
async def delete_book(
    asin: str,
    delete_files: bool = False,
    session: AsyncSession = Depends(get_session)
):
    """Delete a book from database, optionally deleting files."""
    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
        
    await session.delete(book)
    await session.commit()
    return {"message": "Book deleted"}

@router.post("/delete")
async def delete_books(
    asins: list[str],
    delete_files: bool = False,
    session: AsyncSession = Depends(get_session)
):
    """Bulk delete books."""
    for asin in asins:
        result = await session.execute(select(Book).where(Book.asin == asin))
        book = result.scalar_one_or_none()
        if book:
            await session.delete(book)
            
    await session.commit()
    return {"message": f"{len(asins)} books deleted"}

@router.post("/sync")
async def sync_library(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session)
):
    """Trigger an Audible library sync."""
    job = Job(
        task_type=JobType.SYNC,
        status=JobStatus.PENDING,
        progress_percent=0,
    )
    session.add(job)
    await session.commit()
    
    return {
        "job_id": job.id,
        "message": "Library sync queued. Check /jobs for progress.",
        "books_found": 0
    }

@router.post("/{asin}/scan")
async def scan_book(
    asin: str,
    force: bool = False,
    session: AsyncSession = Depends(get_session)
):
    """Scan a specific book's converted file for metadata."""
    success = await library_manager.scan_book(session, asin, force=force)
    await session.commit()
    
    if not success:
        raise HTTPException(status_code=400, detail="Scan failed. Ensure file exists.")
        
    return {
        "job_id": None,
        "message": "Scan completed.",
        "books_found": 1
    }

@router.post("/scan")
async def scan_library(
    background_tasks: BackgroundTasks,
    force: bool = False,
    session: AsyncSession = Depends(get_session)
):
    """Trigger library-wide metadata scan."""
    job = Job(task_type=JobType.REPAIR, status=JobStatus.PENDING, progress_percent=0)
    session.add(job)
    await session.commit()
    
    background_tasks.add_task(library_manager.scan_library, session, force=force)
    
    return {
        "job_id": job.id,
        "message": "Library metadata scan queued. Check /jobs for progress.",
        "books_found": 0
    }

@router.get("/{asin}/details", response_model=BookDetailsResponse)
async def get_book_details(
    asin: str,
    session: AsyncSession = Depends(get_session),
) -> BookDetailsResponse:
    """Fetch all enriched metadata for a book, including chapters and technical info."""
    # 1. Fetch main book
    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # 4. Authors
    result = await session.execute(
        select(Person.name, Person.id)
        .join(BookAuthor, Person.id == BookAuthor.person_id)
        .where(BookAuthor.book_asin == asin)
        .order_by(BookAuthor.ordinal)
    )
    authors = [PersonResponse(name=row[0], asin=None) for row in result.all()]

    # 5. Narrators
    result = await session.execute(
        select(Person.name)
        .join(BookNarrator, Person.id == BookNarrator.person_id)
        .where(BookNarrator.book_asin == asin)
        .order_by(BookNarrator.ordinal)
    )
    narrators = [PersonResponse(name=row[0], asin=None) for row in result.all()]

    # 6. Series
    result = await session.execute(
        select(Series.name, BookSeries.series_index)
        .join(BookSeries, Series.id == BookSeries.series_id)
        .where(BookSeries.book_asin == asin)
    )
    series_row = result.first()
    series = None
    if series_row:
        series = SeriesResponse(name=series_row[0], sequence=series_row[1])

    # 7. Chapters
    chapters_result = await session.execute(
        select(Chapter)
        .where(Chapter.book_asin == asin)
        .order_by(Chapter.start_offset_ms)
    )
    chapters = [
        ChapterResponse(
            index=c.index,
            title=c.title,
            start_offset_ms=c.start_offset_ms,
            length_ms=c.length_ms,
            end_offset_ms=c.end_offset_ms
        ) for c in chapters_result.scalars().all()
    ]

    # 8. Technical & Assets
    tech_result = await session.execute(select(BookTechnical).where(BookTechnical.book_asin == asin))
    tech_row = tech_result.scalar_one_or_none()
    technical = None
    if tech_row:
        technical = TechnicalResponse(
            format=tech_row.format,
            bitrate=tech_row.bitrate,
            sample_rate=tech_row.sample_rate,
            channels=tech_row.channels,
            duration_ms=tech_row.duration_ms,
            file_size=tech_row.file_size
        )

    assets_result = await session.execute(select(BookAsset).where(BookAsset.book_asin == asin))
    assets = [
        AssetResponse(
            asset_type=a.asset_type,
            path=a.path,
            mime_type=a.mime_type
        ) for a in assets_result.scalars().all()
    ]

    # 8. Playback Progress
    progress_result = await session.execute(
        select(PlaybackProgress).where(PlaybackProgress.book_asin == asin)
    )
    progress_row = progress_result.scalar_one_or_none()
    progress = None
    if progress_row:
        progress = PlaybackProgressResponse(
            book_asin=progress_row.book_asin,
            position_ms=progress_row.position_ms,
            last_chapter_id=progress_row.last_chapter_id,
            playback_speed=progress_row.playback_speed,
            is_finished=progress_row.is_finished,
            last_played_at=progress_row.last_played_at,
            completed_at=progress_row.completed_at
        )

    # 9. Compute cover URL
    cover_url = None
    cover_asset = next((a for a in assets if a.asset_type == "cover"), None)
    if cover_asset:
        cover_url = f"/api/library/{asin}/cover"
    
    if not cover_url and book.local_path_cover:
        cover_url = f"/api/library/{asin}/cover"

    metadata_json = book.metadata_json if isinstance(book.metadata_json, dict) else {}

    return BookDetailsResponse(
        asin=asin,
        title=book.title,
        subtitle=book.subtitle,
        description=metadata_json.get("description"),
        authors=authors,
        narrators=narrators,
        series=series,
        genres=metadata_json.get("genres", []),
        publisher=book.publisher,
        release_date=book.release_date,
        language=book.language,
        chapters=chapters,
        technical=technical,
        assets=assets,
        playback_progress=progress,
        cover_url=cover_url,
        duration_total_ms=technical.duration_ms if technical else None
    )


@router.get("/{asin}/cover")
async def get_book_cover(
    asin: str,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Serve the book cover image."""
    result = await session.execute(
        select(BookAsset).where(BookAsset.book_asin == asin, BookAsset.asset_type == "cover")
    )
    asset = result.scalar_one_or_none()
    if asset and Path(asset.path).exists():
        return FileResponse(asset.path)

    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()
    if book and book.local_path_cover and Path(book.local_path_cover).exists():
        return FileResponse(book.local_path_cover)

    raise HTTPException(status_code=404, detail="Cover not found")


@router.patch("/{asin}/progress", response_model=PlaybackProgressResponse)
async def update_progress(
    asin: str,
    update_data: UpdateProgressRequest,
    session: AsyncSession = Depends(get_session),
) -> PlaybackProgressResponse:
    """Update playback progress."""
    result = await session.execute(select(Book).where(Book.asin == asin))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Book not found")

    result = await session.execute(select(PlaybackProgress).where(PlaybackProgress.book_asin == asin))
    progress = result.scalar_one_or_none()

    now = datetime.utcnow()

    if not progress:
        progress = PlaybackProgress(
            book_asin=asin,
            position_ms=update_data.position_ms,
            playback_speed=update_data.playback_speed,
            is_finished=update_data.is_finished,
            last_chapter_id=update_data.chapter_id,
            last_played_at=now,
            completed_at=now if update_data.is_finished else None
        )
        session.add(progress)
    else:
        progress.position_ms = update_data.position_ms
        progress.playback_speed = update_data.playback_speed
        progress.last_chapter_id = update_data.chapter_id
        progress.last_played_at = now
        if update_data.is_finished:
            progress.is_finished = True
            if not progress.completed_at:
                progress.completed_at = now
        elif update_data.is_finished is False and progress.is_finished:
             progress.is_finished = False
             progress.completed_at = None

    await session.commit()
    await session.refresh(progress)

    return PlaybackProgressResponse(
        book_asin=progress.book_asin,
        position_ms=progress.position_ms,
        last_chapter_id=progress.last_chapter_id,
        playback_speed=progress.playback_speed,
        is_finished=progress.is_finished,
        last_played_at=progress.last_played_at,
        completed_at=progress.completed_at
    )
