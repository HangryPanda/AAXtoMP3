"""Audio streaming endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from db.models import Book, BookStatus, LocalItem
from db.session import get_session

router = APIRouter()

# Media type mappings
MEDIA_TYPES = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".m4b": "audio/mp4",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
}


@router.get("/{asin}")
async def stream_audio(
    asin: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """
    Stream converted audio file by ASIN.

    Supports HTTP Range headers for seeking.
    Uses FileResponse for zero-copy streaming (no RAM loading).
    """
    # Get book from database
    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail=f"Book with ASIN {asin} not found")

    if book.status != BookStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Book is not ready for streaming. Current status: {book.status.value}",
        )

    if not book.local_path_converted:
        raise HTTPException(status_code=404, detail="Converted file path not found")

    file_path = Path(book.local_path_converted)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Converted file not found on disk")

    # Determine media type
    suffix = file_path.suffix.lower()
    media_type = MEDIA_TYPES.get(suffix, "application/octet-stream")

    # Use FileResponse which handles Range requests automatically
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=file_path.name,
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.get("/local/{local_id}")
async def stream_local_audio(
    local_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """
    Stream a local-only converted file by LocalItem id.

    Supports HTTP Range headers for seeking.
    """
    try:
        from uuid import UUID

        uid = UUID(local_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid local_id")

    result = await session.execute(select(LocalItem).where(LocalItem.id == uid))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Local item not found")

    file_path = Path(item.output_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Converted file not found on disk")

    settings = get_settings()
    resolved = file_path.resolve()
    allowed_roots = [settings.converted_dir.resolve(), settings.completed_dir.resolve()]
    if not any(str(resolved).startswith(str(root) + "/") or resolved == root for root in allowed_roots):
        raise HTTPException(status_code=403, detail="File path is outside allowed media directories")

    suffix = file_path.suffix.lower()
    media_type = MEDIA_TYPES.get(suffix, "application/octet-stream")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=file_path.name,
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.get("/{asin}/info")
async def get_stream_info(
    asin: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get information about an audio stream."""
    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail=f"Book with ASIN {asin} not found")

    if not book.local_path_converted:
        return {
            "available": False,
            "asin": asin,
            "status": book.status.value,
        }

    file_path = Path(book.local_path_converted)
    exists = file_path.exists()

    return {
        "available": exists and book.status == BookStatus.COMPLETED,
        "asin": asin,
        "title": book.title,
        "status": book.status.value,
        "format": book.conversion_format,
        "file_size": file_path.stat().st_size if exists else None,
        "media_type": MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream") if exists else None,
    }
