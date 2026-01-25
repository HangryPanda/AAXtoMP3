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

_scan_in_flight: set[str] = set()
_scan_in_flight_lock = asyncio.Lock()


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


class PartialDownloadItem(BaseModel):
    """A book with partial download (cover only, no aaxc file)."""
    asin: str
    title: str
    cover_path: str | None
    downloaded_at: str | None
    book: BookRead | None  # Full book data if available in DB


class PartialDownloadsResponse(BaseModel):
    """Response for partial downloads endpoint."""
    items: list[PartialDownloadItem]
    total: int


@router.get("/downloads/incomplete", response_model=PartialDownloadsResponse)
async def get_incomplete_downloads(
    session: AsyncSession = Depends(get_session),
) -> PartialDownloadsResponse:
    """
    Get books with partial downloads (cover downloaded but no aaxc file).

    These need to be re-downloaded before conversion is possible.
    """
    from core.config import get_settings

    settings = get_settings()
    manifest_path = settings.manifest_dir / "download_manifest.json"

    if not manifest_path.exists():
        return PartialDownloadsResponse(items=[], total=0)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("Failed to read download manifest: %s", e)
        return PartialDownloadsResponse(items=[], total=0)

    # Find entries with partial status
    partial_asins = [
        asin for asin, entry in manifest.items()
        if entry.get("status") == "partial"
    ]

    if not partial_asins:
        return PartialDownloadsResponse(items=[], total=0)

    # Fetch book data for these ASINs
    result = await session.execute(
        select(Book).where(Book.asin.in_(partial_asins))
    )
    books_by_asin = {book.asin: book for book in result.scalars().all()}

    items = []
    for asin in partial_asins:
        entry = manifest[asin]
        book = books_by_asin.get(asin)
        items.append(PartialDownloadItem(
            asin=asin,
            title=entry.get("title", asin),
            cover_path=entry.get("cover_path") or None,
            downloaded_at=entry.get("downloaded_at"),
            book=BookRead.model_validate(book) if book else None,
        ))

    return PartialDownloadsResponse(items=items, total=len(items))


@router.get("")
async def get_books(
    session: AsyncSession = Depends(get_session),
    skip: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1, le=500),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=500),
    q: str | None = None,
    search: str | None = None,
    author: str | None = None,
    series: str | None = None,
    series_title: str | None = None,
    status: BookStatus | None = None,
    content_type: Literal["audiobook", "podcast"] | None = None,
    has_local: bool | None = None,
    since: str | None = None,
    sort_by: Literal[
        "title",
        "author",
        "release_date",
        "purchase_date",
        "runtime",
        "runtime_length_min",
        "created_at",
        "updated_at",
    ] = "title",
    sort_dir: Literal["asc", "desc"] = "asc",
):
    """List books with filtering, search, and pagination."""
    # Back-compat aliases for older/front-end params
    if q is None and search:
        q = search
    if series is None and series_title:
        series = series_title

    # Pagination: support either (skip, limit) or (page, page_size)
    effective_limit = limit if limit is not None else 100
    effective_skip = skip if skip is not None else 0
    effective_page = 1
    effective_page_size = effective_limit
    if page is not None or page_size is not None:
        effective_page = page or 1
        effective_page_size = page_size or 100
        effective_limit = effective_page_size
        effective_skip = (effective_page - 1) * effective_page_size

    statement = select(Book)
    
    # 1. Filters
    if q:
        statement = statement.where(
            or_(
                Book.title.ilike(f"%{q}%"),
                Book.subtitle.ilike(f"%{q}%"),
                Book.authors_json.ilike(f"%{q}%"),
                Book.narrators_json.ilike(f"%{q}%")
            )
        )
    if author:
        statement = statement.where(Book.authors_json.ilike(f"%{author}%"))
    if status:
        statement = statement.where(Book.status == status)
    if series:
        statement = statement.where(Book.series_json.ilike(f"%{series}%"))
    if has_local is not None:
        has_any_local = or_(
            Book.local_path_aax.is_not(None),
            Book.local_path_converted.is_not(None),
        )
        statement = statement.where(has_any_local if has_local else ~has_any_local)

    if content_type is not None:
        ct_expr = func.coalesce(
            Book.metadata_json["content_type"].as_string(),
            Book.metadata_json["contentType"].as_string(),
        )
        if content_type == "podcast":
            statement = statement.where(func.lower(ct_expr) == "podcast")
        else:
            statement = statement.where(or_(ct_expr.is_(None), func.lower(ct_expr) != "podcast"))

    if since:
        since_dt: datetime | None = None
        try:
            raw = since.strip()
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            since_dt = datetime.fromisoformat(raw)
        except Exception:
            since_dt = None
        if since_dt is not None:
            statement = statement.where(Book.updated_at >= since_dt)

    # 2. Total Count (before pagination)
    count_statement = select(func.count()).select_from(statement.subquery())
    total_result = await session.execute(count_statement)
    total = total_result.scalar() or 0

    # 3. Sorting
    if sort_by in ("runtime", "runtime_length_min"):
        order_col = Book.runtime_length_min
    else:
        order_col = getattr(Book, sort_by)
    if sort_dir == "desc":
        statement = statement.order_by(order_col.desc())
    else:
        statement = statement.order_by(order_col.asc())

    # 4. Pagination
    statement = statement.offset(effective_skip).limit(effective_limit)
    
    result = await session.execute(statement)
    books = result.scalars().all()

    total_pages = int((total + effective_limit - 1) / effective_limit) if effective_limit else 0

    return {
        "total": total,
        "skip": effective_skip,
        "limit": effective_limit,
        # Convenience pagination fields (safe to ignore for clients that use skip/limit)
        "page": effective_page,
        "page_size": effective_page_size,
        "total_pages": total_pages,
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
    try:
        uid = UUID(local_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid local_id")

    result = await session.execute(select(LocalItem).where(LocalItem.id == uid))
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

def _delete_book_files(book: Book) -> None:
    """Delete local files associated with a book."""
    paths = [
        book.local_path_aax,
        book.local_path_voucher,
        book.local_path_cover,
        book.local_path_converted,
    ]
    for p in paths:
        if p:
            try:
                path_obj = Path(p)
                if path_obj.exists() and path_obj.is_file():
                    path_obj.unlink()
                    logger.info(f"Deleted file for {book.asin}: {p}")
            except Exception as e:
                logger.warning(f"Failed to delete file {p}: {e}")

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
        
    if delete_files:
        _delete_book_files(book)

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
            if delete_files:
                _delete_book_files(book)
            await session.delete(book)
            
    await session.commit()
    return {"message": f"{len(asins)} books deleted"}

@router.post("/sync", status_code=202)
async def sync_library(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session)
):
    """Trigger an Audible library sync."""
    from api.routes.jobs import job_manager

    job = Job(
        task_type=JobType.SYNC,
        status=JobStatus.PENDING,
        progress_percent=0,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Queue job for execution
    await job_manager.queue_sync(job.id)

    return {
        "job_id": str(job.id),
        "status": JobStatus.QUEUED.value,
        "message": "Library sync queued. Check /jobs for progress.",
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

    # 7. Technical & Assets (needed for duration)
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

    # 8. Chapters
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
        )
        for c in chapters_result.scalars().all()
    ]

    db_chapters_missing = len(chapters) == 0

    duration_total_ms: int | None = None
    if technical and technical.duration_ms:
        duration_total_ms = technical.duration_ms
    elif book.runtime_length_min:
        duration_total_ms = int(book.runtime_length_min) * 60 * 1000

    bind = session.bind
    if db_chapters_missing:

        async def _scan_if_needed() -> None:
            logger.info("Background chapter scan task started for %s", asin)
            if not book.local_path_converted:
                logger.debug("Book %s has no local_path_converted, skipping background scan", asin)
                return
            converted_path = Path(book.local_path_converted)
            if not converted_path.exists():
                logger.debug("Converted file for %s not found at %s, skipping background scan", asin, converted_path)
                return

            async with _scan_in_flight_lock:
                if asin in _scan_in_flight:
                    logger.debug("Scan already in flight for %s, skipping", asin)
                    return
                _scan_in_flight.add(asin)
                logger.debug("Added %s to scan_in_flight set", asin)

            try:
                if bind is None:
                    logger.debug("No database bind available for background scan of %s", asin)
                    return
                from sqlalchemy.orm import sessionmaker

                async_session_maker = sessionmaker(
                    bind=bind,
                    class_=AsyncSession,
                    expire_on_commit=False,
                )
                logger.info("Starting background chapter extraction for %s", asin)
                async with async_session_maker() as bg_session:
                    result = await library_manager.scan_book(bg_session, asin, force=False)
                    logger.info("Background chapter extraction for %s completed: %s", asin, result)
            except Exception:
                logger.exception("Background scan failed for %s", asin)
            finally:
                async with _scan_in_flight_lock:
                    _scan_in_flight.discard(asin)

        asyncio.create_task(_scan_if_needed(), name=f"scan-book-missing-chapters:{asin}")

    chapters_synthetic = False
    if db_chapters_missing and duration_total_ms and duration_total_ms > 0:
        chapters = [
            ChapterResponse(
                index=0,
                title="Full Duration",
                start_offset_ms=0,
                length_ms=duration_total_ms,
                end_offset_ms=duration_total_ms,
            )
        ]
        chapters_synthetic = True

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
        duration_total_ms=duration_total_ms,
        chapters_synthetic=chapters_synthetic,
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


@router.get("/{asin}/progress")
async def get_progress(
    asin: str,
    session: AsyncSession = Depends(get_session),
) -> PlaybackProgressResponse | None:
    """Get playback progress for a book. Returns null if no progress exists."""
    result = await session.execute(select(Book).where(Book.asin == asin))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Book not found")

    result = await session.execute(select(PlaybackProgress).where(PlaybackProgress.book_asin == asin))
    progress = result.scalar_one_or_none()

    if not progress:
        return None

    return PlaybackProgressResponse(
        book_asin=progress.book_asin,
        position_ms=progress.position_ms,
        last_chapter_id=progress.last_chapter_id,
        playback_speed=progress.playback_speed,
        is_finished=progress.is_finished,
        last_played_at=progress.last_played_at,
        completed_at=progress.completed_at
    )
