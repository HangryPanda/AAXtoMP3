"""Library management endpoints."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID
import json
from collections.abc import Iterable

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.jobs import job_manager
from db.models import (
    Book,
    BookRead,
    BookStatus,
    BookUpdate,
    Job,
    JobStatus,
    JobType,
    LocalItem,
    LocalItemRead,
)
from db.session import async_session_maker, get_session
from core.config import get_settings
from services.audible_client import AudibleClient

router = APIRouter()
logger = logging.getLogger(__name__)

def _as_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _extract_contributors(item: dict) -> list[dict]:
    raw = item.get("contributors")
    if isinstance(raw, dict):
        # Common shapes:
        # - {"items": [...]} (audible API)
        # - {"contributors": [...]} (wrapper)
        # - {"authors": [...], "narrators": [...], ...} (grouped by role)
        raw_items = raw.get("items") or raw.get("contributors")
        if raw_items is not None:
            raw = raw_items
        else:
            flattened: list[object] = []
            for v in raw.values():
                if isinstance(v, dict) and ("items" in v or "contributors" in v):
                    flattened.extend(_as_list(v.get("items") or v.get("contributors")))
                else:
                    flattened.extend(_as_list(v))
            raw = flattened
    contribs = _as_list(raw)
    return [c for c in contribs if isinstance(c, dict)]


def _extract_people(item: dict, kind: Literal["author", "narrator"]) -> list[dict[str, str]]:
    # 1) Direct fields
    direct = item.get("authors" if kind == "author" else "narrators")
    if isinstance(direct, str):
        # TSV-style or simplified API responses sometimes return a plain string
        names = [n.strip() for n in direct.replace("&", ",").split(",") if n.strip()]
        return [{"name": n} for n in names]
    if isinstance(direct, dict):
        direct = direct.get("items") or direct.get("contributors") or direct.get("narrators") or direct.get("authors")
    people = []
    for entry in _as_list(direct):
        if isinstance(entry, str) and entry.strip():
            people.append({"name": entry.strip()})
        elif isinstance(entry, dict):
            name = (
                entry.get("name")
                or entry.get("display_name")
                or entry.get("full_name")
                or entry.get("title")
            )
            if isinstance(name, str) and name.strip():
                person: dict[str, str] = {"name": name.strip()}
                asin = entry.get("asin")
                if isinstance(asin, str) and asin.strip():
                    person["asin"] = asin.strip()
                people.append(person)

    if people:
        return people

    # 1b) Other common single-field variants
    alt_key = "author" if kind == "author" else "narrator"
    alt = item.get(alt_key) or item.get(f"{alt_key}_name")
    if isinstance(alt, str) and alt.strip():
        names = [n.strip() for n in alt.replace("&", ",").split(",") if n.strip()]
        return [{"name": n} for n in names]

    # 2) Contributors list (Audible API response_groups=contributors)
    role_needles = ["author"] if kind == "author" else ["narrator", "reader"]
    for c in _extract_contributors(item):
        role = c.get("role") or c.get("type") or c.get("contributor_type") or c.get("contributor_role")
        role_str = str(role).lower() if role is not None else ""
        if any(needle in role_str for needle in role_needles):
            name = c.get("name") or c.get("display_name") or c.get("full_name") or c.get("title")
            if isinstance(name, str) and name.strip():
                person = {"name": name.strip()}
                asin = c.get("asin")
                if isinstance(asin, str) and asin.strip():
                    person["asin"] = asin.strip()
                people.append(person)

    return people


def _extract_product_images(item: dict) -> dict[str, str] | None:
    raw = (
        item.get("product_images")
        or item.get("productImages")
        or item.get("images")
        or item.get("cover_url")
        or item.get("coverUrl")
        or item.get("image_url")
        or item.get("imageUrl")
    )
    if isinstance(raw, str):
        url = raw.strip()
        if not url:
            return None
        if url.startswith("http://"):
            url = "https://" + url.removeprefix("http://")
        # Prefer the same keys the frontend looks for.
        return {"500": url, "250": url}
    if isinstance(raw, dict):
        images: dict[str, str] = {}
        for k, v in raw.items():
            url: str | None = None
            if isinstance(v, str):
                url = v
            elif isinstance(v, dict):
                candidate = v.get("url") or v.get("image_url") or v.get("src")
                if isinstance(candidate, str):
                    url = candidate
            if url:
                if url.startswith("http://"):
                    url = "https://" + url.removeprefix("http://")
                images[str(k)] = url
        return images or None

    if isinstance(raw, list):
        images = {}
        for idx, v in enumerate(raw):
            if not isinstance(v, dict):
                continue
            url = v.get("url") or v.get("image_url") or v.get("src")
            if not isinstance(url, str) or not url:
                continue
            if url.startswith("http://"):
                url = "https://" + url.removeprefix("http://")
            key = v.get("width") or v.get("size") or v.get("height") or idx
            images[str(key)] = url
        return images or None

    return None


@router.get("/debug/raw")
async def debug_raw_library(limit: int = 1) -> dict:
    """
    Debug endpoint: returns raw items from Audible library fetch.

    Enabled only when API `DEBUG=true` to avoid leaking data in production.
    """
    settings = get_settings()
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")

    client = AudibleClient()
    items = await client.get_library(limit=limit)
    return {"count": len(items), "items": items[:limit]}


@router.get("/{asin}/raw")
async def get_book_raw(
    asin: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Return the raw stored Audible metadata blob for a single book.

    Not returned by default in list/detail endpoints to keep payloads small.
    """
    settings = get_settings()
    # Always require DEBUG=true for raw metadata access.
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")

    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail=f"Book with ASIN {asin} not found")

    if not book.metadata_json:
        raise HTTPException(status_code=404, detail="Raw metadata not available for this book")

    # metadata_json is stored as JSON (dict/list); return as-is
    return {"asin": asin, "metadata": book.metadata_json}


class PaginatedBooksResponse(BaseModel):
    """Paginated books response."""

    items: list[BookRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedLocalItemsResponse(BaseModel):
    items: list[LocalItemRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class SyncResponse(BaseModel):
    """Library sync response."""

    job_id: str
    status: Literal["queued", "started", "already_running"]
    message: str


class SyncStatusResponse(BaseModel):
    last_sync_completed_at: datetime | None
    last_sync_job_id: str | None
    total_books: int


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    session: AsyncSession = Depends(get_session),
) -> SyncStatusResponse:
    """Return last successful sync time and current library size."""
    # last completed sync job
    stmt = (
        select(Job)
        .where(Job.task_type == JobType.SYNC)
        .where(Job.status == JobStatus.COMPLETED)
        .order_by(Job.completed_at.desc().nullslast(), Job.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    count_result = await session.execute(select(func.count()).select_from(Book))
    total_books = int(count_result.scalar() or 0)

    return SyncStatusResponse(
        last_sync_completed_at=job.completed_at if job else None,
        last_sync_job_id=str(job.id) if job else None,
        total_books=total_books,
    )


class SeriesOption(BaseModel):
    title: str
    asin: str | None = None
    count: int


class SeriesOptionsResponse(BaseModel):
    items: list[SeriesOption]
    no_series_count: int


class RepairPreviewResponse(BaseModel):
    remote_total: int
    downloaded_total: int
    converted_total: int
    converted_of_downloaded: int
    orphan_downloads: int
    orphan_conversions: int
    missing_files: int
    duplicate_conversions: int
    generated_at: datetime


class RepairApplyResponse(BaseModel):
    job_id: str
    status: Literal["queued"]
    message: str


class RepairDryRunResponse(BaseModel):
    """Debug-only: show what repair would do for a single ASIN."""

    asin: str
    in_remote_catalog: bool
    has_download_manifest: bool
    has_converted_manifest: bool
    download: dict[str, Any] | None = None
    download_files: dict[str, bool] | None = None
    conversions: list[dict[str, Any]] | None = None
    chosen_conversion: dict[str, Any] | None = None
    local_item_exists: bool | None = None
    local_item_id: str | None = None
    current_book: dict[str, Any] | None = None
    proposed_book_updates: dict[str, Any] | None = None
    proposed_local_item_insert: dict[str, Any] | None = None
    notes: list[str] = []


@router.get("/series", response_model=SeriesOptionsResponse)
async def list_series(
    session: AsyncSession = Depends(get_session),
) -> SeriesOptionsResponse:
    """
    Return distinct series titles found in the library for UI filtering.

    Note: series is stored as JSON-string data in `series_json`, so we aggregate in Python.
    """
    result = await session.execute(select(Book.series_json))
    rows = result.all()

    counts: dict[str, SeriesOption] = {}
    no_series_count = 0

    for (series_json,) in rows:
        if not series_json:
            no_series_count += 1
            continue

        try:
            parsed = json.loads(series_json)
        except Exception:
            continue

        if not isinstance(parsed, list):
            continue

        for entry in parsed:
            if not isinstance(entry, dict):
                continue
            title = entry.get("title")
            if not isinstance(title, str) or not title.strip():
                continue
            title = title.strip()
            asin = entry.get("asin")
            asin_str = asin.strip() if isinstance(asin, str) and asin.strip() else None

            existing = counts.get(title)
            if existing is None:
                counts[title] = SeriesOption(title=title, asin=asin_str, count=1)
            else:
                existing.count += 1
                if existing.asin is None and asin_str is not None:
                    existing.asin = asin_str

    items = sorted(counts.values(), key=lambda s: s.title.lower())
    return SeriesOptionsResponse(items=items, no_series_count=no_series_count)


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
        generated_at=datetime.now(UTC),
    )


@router.post("/repair/apply", response_model=RepairApplyResponse, status_code=202)
async def repair_apply(
    session: AsyncSession = Depends(get_session),
) -> RepairApplyResponse:
    """Queue a repair job that reconciles DB with manifests + filesystem."""
    from db.models import Job
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


@router.get("/repair/dry-run/{asin}", response_model=RepairDryRunResponse)
async def repair_dry_run(
    asin: str,
    session: AsyncSession = Depends(get_session),
) -> RepairDryRunResponse:
    """Debug-only: compute per-ASIN repair actions without mutating the DB."""
    if not get_settings().debug:
        raise HTTPException(status_code=404, detail="Not found")

    from services.repair_pipeline import compute_dry_run

    try:
        payload = await compute_dry_run(session, asin)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return RepairDryRunResponse.model_validate(payload)


@router.get("", response_model=PaginatedBooksResponse)
async def get_books(
    session: AsyncSession = Depends(get_session),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
    status: BookStatus | None = Query(default=None, description="Filter by status"),
    search: str | None = Query(default=None, description="Search in title, author, narrator"),
    series_title: str | None = Query(default=None, description="Filter by series title (use '__none__' for no series)"),
    has_local: bool | None = Query(default=None, description="If true, only return items with local files"),
    sort_by: Literal["title", "purchase_date", "runtime_length_min", "created_at"] = Query(
        default="purchase_date", description="Sort field"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc", description="Sort order"),
    since: datetime | None = Query(default=None, description="Only return books modified after this timestamp"),
) -> PaginatedBooksResponse:
    """Get paginated list of books with optional filtering and sorting."""
    # Build base query
    query = select(Book)

    # Apply filters
    if status:
        query = query.where(Book.status == status)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Book.title.ilike(search_term))
            | (Book.authors_json.ilike(search_term))
            | (Book.narrators_json.ilike(search_term))
        )

    if has_local is True:
        query = query.where(Book.status != BookStatus.NEW)

    if series_title:
        if series_title == "__none__":
            query = query.where(Book.series_json.is_(None))
        else:
            series_term = f"%{series_title}%"
            query = query.where(Book.series_json.ilike(series_term))

    if since:
        query = query.where(Book.updated_at > since)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    sort_column = getattr(Book, sort_by, Book.purchase_date)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute query
    result = await session.execute(query)
    books = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size

    return PaginatedBooksResponse(
        items=[BookRead.model_validate(book) for book in books],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/local", response_model=PaginatedLocalItemsResponse)
async def get_local_items(
    session: AsyncSession = Depends(get_session),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
    search: str | None = Query(default=None, description="Search in title/authors"),
) -> PaginatedLocalItemsResponse:
    query = select(LocalItem)

    if search:
        term = f"%{search}%"
        query = query.where((LocalItem.title.ilike(term)) | (LocalItem.authors.ilike(term)))

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = int(total_result.scalar() or 0)

    query = query.order_by(LocalItem.updated_at.desc(), LocalItem.created_at.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    items = result.scalars().all()
    total_pages = (total + page_size - 1) // page_size

    return PaginatedLocalItemsResponse(
        items=[LocalItemRead.model_validate(it) for it in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/local/{local_id}", response_model=LocalItemRead)
async def get_local_item(
    local_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> LocalItemRead:
    result = await session.execute(select(LocalItem).where(LocalItem.id == local_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Local item not found")
    return LocalItemRead.model_validate(item)


@router.get("/{asin}", response_model=BookRead)
async def get_book(
    asin: str,
    session: AsyncSession = Depends(get_session),
) -> BookRead:
    """Get a single book by ASIN."""
    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail=f"Book with ASIN {asin} not found")

    # Lazy load chapters if missing
    import json
    metadata = {}
    if book.metadata_json:
        if isinstance(book.metadata_json, str):
            try:
                metadata = json.loads(book.metadata_json)
            except:
                metadata = {}
        elif isinstance(book.metadata_json, dict):
            metadata = book.metadata_json
            
    if "chapters" not in metadata or not metadata["chapters"]:
        # Fetch chapters
        try:
            client = AudibleClient()
            if await client.is_authenticated():
                chapters = await client.get_chapters(asin)
                if chapters:
                    metadata["chapters"] = chapters
                    # Update DB
                    # Note: book.metadata_json is typed as str|None in Pydantic but mapped to JSON in SQLAlchemy
                    # Assigning a dict should work for SQLAlchemy
                    book.metadata_json = metadata 
                    session.add(book)
                    await session.commit()
                    await session.refresh(book)
        except Exception as e:
            # Log but don't fail request
            print(f"Failed to lazy load chapters: {e}")

    return BookRead.model_validate(book)


@router.patch("/{asin}", response_model=BookRead)
async def update_book(
    asin: str,
    book_update: BookUpdate,
    session: AsyncSession = Depends(get_session),
) -> BookRead:
    """Update a book's metadata or status."""
    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail=f"Book with ASIN {asin} not found")

    # Update fields
    update_data = book_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(book, field, value)

    book.updated_at = datetime.utcnow()
    session.add(book)
    await session.commit()
    await session.refresh(book)

    return BookRead.model_validate(book)


class BatchDeleteRequest(BaseModel):
    """Request body for batch delete."""
    asins: list[str]


@router.delete("/{asin}", status_code=204)
async def delete_book(
    asin: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a book from the library."""
    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail=f"Book with ASIN {asin} not found")

    await session.delete(book)
    await session.commit()


@router.post("/delete", status_code=200)
async def delete_books(
    request: BatchDeleteRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    """Batch delete books."""
    if not request.asins:
        return {"deleted": 0}

    # SQLAlchemy 'in_' requires a tuple or list
    stmt = select(Book).where(Book.asin.in_(request.asins))
    result = await session.execute(stmt)
    books = result.scalars().all()

    count = 0
    for book in books:
        await session.delete(book)
        count += 1

    await session.commit()

    return {"deleted": count}


@router.post("/sync", response_model=SyncResponse, status_code=202)
async def sync_library(
    session: AsyncSession = Depends(get_session),
) -> SyncResponse:
    """Trigger Audible library sync."""
    # Create a new sync job record
    job = Job(
        task_type=JobType.SYNC,
        status=JobStatus.PENDING,
        progress_percent=0,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Queue job for execution via JobManager
    await job_manager.queue_sync(job.id)

    return SyncResponse(
        job_id=str(job.id),
        status="queued",
        message="Library sync queued. Check /jobs for progress.",
    )
