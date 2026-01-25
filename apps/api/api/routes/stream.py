"""Audio streaming endpoints with JIT transcoding fallback."""

import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from db.models import Book, BookStatus, LocalItem
from db.session import get_session
from services.jit_streaming import JITStreamingError, JITStreamingService

logger = logging.getLogger(__name__)

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

# Singleton JIT service instance
_jit_service: JITStreamingService | None = None


def get_jit_service() -> JITStreamingService:
    """Get or create JIT streaming service singleton."""
    global _jit_service
    if _jit_service is None:
        _jit_service = JITStreamingService()
    return _jit_service


def _has_converted_file(book: Book) -> tuple[bool, Path | None]:
    """Check if book has a valid converted file on disk."""
    if not book.local_path_converted:
        return (False, None)
    file_path = Path(book.local_path_converted)
    if not file_path.exists():
        return (False, None)
    return (True, file_path)


def _has_source_file(book: Book) -> tuple[bool, Path | None]:
    """Check if book has a valid AAX/AAXC source file on disk."""
    if not book.local_path_aax:
        return (False, None)
    file_path = Path(book.local_path_aax)
    if not file_path.exists():
        return (False, None)
    return (True, file_path)


@router.get("/{asin}", response_model=None)
async def stream_audio(
    asin: str,
    request: Request,
    start_time: float | None = Query(
        default=None,
        ge=0,
        description="Start position in seconds (JIT streams only)",
    ),
    session: AsyncSession = Depends(get_session),
) -> FileResponse | StreamingResponse:
    """
    Stream audio file by ASIN with waterfall priority.

    Priority 1: Serve converted file (FileResponse with zero-copy, range support)
    Priority 2: JIT stream from AAX/AAXC source (StreamingResponse)

    Supports HTTP Range headers for converted files.
    For JIT streams, use ?start_time=<seconds> for seeking.
    """
    # Get book from database
    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail=f"Book with ASIN {asin} not found")

    # Priority 1: Serve converted file if available
    has_converted, converted_path = _has_converted_file(book)
    if has_converted and converted_path:
        # For converted files, require COMPLETED status
        if book.status != BookStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Book is not ready for streaming. Current status: {book.status.value}",
            )

        suffix = converted_path.suffix.lower()
        media_type = MEDIA_TYPES.get(suffix, "application/octet-stream")

        logger.debug("Serving converted file for %s: %s", asin, converted_path)
        return FileResponse(
            path=converted_path,
            media_type=media_type,
            filename=converted_path.name,
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600",
            },
        )

    # Priority 2: JIT stream from source file
    has_source, source_path = _has_source_file(book)
    if has_source and source_path:
        jit_service = get_jit_service()
        settings = get_settings()

        # Get the output format and determine media type
        output_format = settings.jit_stream_format
        jit_media_types = {
            "mp3": "audio/mpeg",
            "aac": "audio/mp4",
            "opus": "audio/opus",
            "flac": "audio/flac",
        }
        media_type = jit_media_types.get(output_format, "audio/mpeg")

        # Sanitize title for filename
        safe_title = "".join(
            c if c.isalnum() or c in " -_" else "_" for c in (book.title or "audio")
        ).strip()
        filename = f"{safe_title}.{output_format}"

        logger.info(
            "Starting JIT stream for %s from %s (start_time=%s)",
            asin,
            source_path,
            start_time,
        )

        try:
            return StreamingResponse(
                jit_service.stream_audio(book, start_time=start_time),
                media_type=media_type,
                headers={
                    "Content-Disposition": f'inline; filename="{filename}"',
                    "Cache-Control": "no-cache",
                    "X-Stream-Mode": "jit",
                },
            )
        except JITStreamingError as e:
            logger.error("JIT streaming failed for %s: %s", asin, e)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start JIT stream: {e}",
            )

    # No audio source available. Provide a more specific 404 when the book is marked
    # COMPLETED but the converted file is missing/misconfigured.
    if book.status == BookStatus.COMPLETED:
        if not book.local_path_converted:
            raise HTTPException(
                status_code=404,
                detail="Converted file not found (path not set)",
            )
        raise HTTPException(
            status_code=404,
            detail="Converted file not found on disk",
        )

    raise HTTPException(status_code=404, detail="No audio source available for streaming")


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
    """
    Get information about an audio stream.

    Returns availability status, file info, and JIT streaming capability.
    """
    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail=f"Book with ASIN {asin} not found")

    # Check converted file
    has_converted, converted_path = _has_converted_file(book)
    converted_available = has_converted and book.status == BookStatus.COMPLETED

    # Check JIT availability (source file exists)
    has_source, source_path = _has_source_file(book)

    # For JIT, we also need voucher for AAXC files
    jit_available = False
    if has_source and source_path:
        if source_path.suffix.lower() == ".aaxc":
            # AAXC needs voucher
            jit_available = bool(book.local_path_voucher) and Path(
                book.local_path_voucher
            ).exists()
        else:
            # AAX just needs the file
            jit_available = True

    # Determine stream mode
    stream_mode: Literal["file", "jit"] | None = None
    if converted_available:
        stream_mode = "file"
    elif jit_available:
        stream_mode = "jit"

    response: dict = {
        "available": converted_available or jit_available,
        "jit_available": jit_available,
        "stream_mode": stream_mode,
        "asin": asin,
        "title": book.title,
        "status": book.status.value,
    }

    # Add converted file info if available
    if has_converted and converted_path:
        try:
            file_size = converted_path.stat().st_size
            response.update({
                "format": book.conversion_format,
                "file_size": file_size,
                "media_type": MEDIA_TYPES.get(
                    converted_path.suffix.lower(), "application/octet-stream"
                ),
            })
        except (FileNotFoundError, PermissionError, OSError) as e:
            # File was deleted/moved after exists() check - treat as unavailable
            logger.warning("File stat failed for %s: %s", converted_path, e)
            response["available"] = jit_available  # Fall back to JIT-only availability
            response["stream_mode"] = "jit" if jit_available else None
            response.update({
                "format": None,
                "file_size": None,
                "media_type": None,
            })
    else:
        response.update({
            "format": None,
            "file_size": None,
            "media_type": None,
        })

    # Add JIT stream info if available
    if jit_available:
        settings = get_settings()
        jit_media_types = {
            "mp3": "audio/mpeg",
            "aac": "audio/mp4",
            "opus": "audio/opus",
            "flac": "audio/flac",
        }
        response["jit_format"] = settings.jit_stream_format
        response["jit_bitrate"] = settings.jit_stream_bitrate
        response["jit_media_type"] = jit_media_types.get(
            settings.jit_stream_format, "audio/mpeg"
        )

    return response


@router.get("/jit/status")
async def get_jit_status() -> dict:
    """Get JIT streaming service status."""
    jit_service = get_jit_service()
    settings = get_settings()

    return {
        "active_streams": jit_service.get_active_streams(),
        "stream_count": jit_service.get_stream_count(),
        "max_concurrent": settings.max_jit_streams,
        "default_format": settings.jit_stream_format,
        "default_bitrate": settings.jit_stream_bitrate,
    }


@router.delete("/jit/{asin}")
async def cancel_jit_stream(asin: str) -> dict:
    """
    Cancel an active JIT stream for a book.

    Returns success status and message.
    """
    jit_service = get_jit_service()
    cancelled = await jit_service.cancel_stream(asin)

    if cancelled:
        logger.info("Cancelled JIT stream for %s via API", asin)
        return {
            "success": True,
            "message": f"JIT stream for {asin} cancelled",
            "asin": asin,
        }
    else:
        return {
            "success": False,
            "message": f"No active JIT stream found for {asin}",
            "asin": asin,
        }
