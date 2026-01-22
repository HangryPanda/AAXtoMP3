"""Async job manager with semaphore-based concurrency control."""

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from core.config import get_settings
from db.models import Book, BookStatus
from db.session import get_session
from services.audible_client import AudibleClient
from services.converter_engine import ConverterEngine
from services.repair_pipeline import apply_repair
from sqlalchemy import select

logger = logging.getLogger(__name__)


class StatusUpdateCallback(Protocol):
    """Protocol for job status update callbacks."""

    async def __call__(
        self,
        job_id: UUID,
        status: str,
        progress: int,
        message: str | None = None,
        error: str | None = None,
    ) -> None:
        """
        Called when job status changes.

        Args:
            job_id: The job identifier.
            status: New status string.
            progress: Progress percentage (0-100).
            message: Optional status message.
            error: Optional error message.
        """
        ...


class JobManager:
    """
    Manages background jobs with separate concurrency limits for IO-bound
    (downloads) and CPU-bound (conversions) tasks.
    """

    def __init__(
        self,
        status_callback: StatusUpdateCallback | None = None,
    ) -> None:
        """
        Initialize job manager with semaphores.

        Args:
            status_callback: Optional async callback for status updates.
        """
        settings = get_settings()

        # Separate semaphores for different task types
        self.download_semaphore = asyncio.Semaphore(settings.max_download_concurrent)
        self.convert_semaphore = asyncio.Semaphore(settings.max_convert_concurrent)

        # Track running tasks
        self._tasks: dict[UUID, asyncio.Task[Any]] = {}
        self._cancelled: set[UUID] = set()

        # Progress callbacks per job
        self._progress_callbacks: dict[UUID, Callable[[int, str], None]] = {}

        # Status update callback (for WebSocket integration)
        self._status_callback = status_callback

        # Services
        self.audible_client = AudibleClient()
        self.converter = ConverterEngine()
        self.settings = settings

        logger.info(
            "JobManager initialized with download_concurrent=%d, convert_concurrent=%d",
            settings.max_download_concurrent,
            settings.max_convert_concurrent,
        )

    def set_status_callback(self, callback: StatusUpdateCallback | None) -> None:
        """
        Set the status update callback.

        Args:
            callback: Async callback for status updates, or None to disable.
        """
        self._status_callback = callback

    async def _notify_status(
        self,
        job_id: UUID,
        status: str,
        progress: int,
        message: str | None = None,
        error: str | None = None,
    ) -> None:
        """
        Notify status update via callback if set.

        Args:
            job_id: The job identifier.
            status: New status string.
            progress: Progress percentage.
            message: Optional message.
            error: Optional error message.
        """
        if self._status_callback:
            try:
                await self._status_callback(
                    job_id=job_id,
                    status=status,
                    progress=progress,
                    message=message,
                    error=error,
                )
            except Exception as e:
                logger.warning(
                    "Status callback failed for job %s: %s",
                    job_id,
                    e,
                )

    async def queue_download(
        self,
        job_id: UUID,
        asins: list[str],
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> None:
        """
        Queue a download job.

        Args:
            job_id: Unique job identifier.
            asins: List of ASINs to download.
            progress_callback: Optional callback for progress updates.
        """
        logger.info(
            "Queuing download job %s for %d ASINs: %s",
            job_id,
            len(asins),
            asins[:5],  # Log first 5
        )

        if progress_callback:
            self._progress_callbacks[job_id] = progress_callback

        task = asyncio.create_task(
            self._execute_download(job_id, asins),
            name=f"download-{job_id}",
        )
        self._tasks[job_id] = task

        await self._notify_status(
            job_id,
            "QUEUED",
            0,
            f"Queued for download: {len(asins)} items",
        )

    async def queue_conversion(
        self,
        job_id: UUID,
        asin: str,
        format: str = "m4b",
        naming_scheme: str | None = None,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> None:
        """
        Queue a conversion job.

        Args:
            job_id: Unique job identifier.
            asin: ASIN of book to convert.
            format: Output format.
            naming_scheme: Optional naming scheme.
            progress_callback: Optional callback for progress updates.
        """
        logger.info(
            "Queuing conversion job %s for ASIN %s (format=%s)",
            job_id,
            asin,
            format,
        )

        if progress_callback:
            self._progress_callbacks[job_id] = progress_callback

        task = asyncio.create_task(
            self._execute_conversion(job_id, asin, format, naming_scheme),
            name=f"convert-{job_id}",
        )
        self._tasks[job_id] = task

        await self._notify_status(
            job_id,
            "QUEUED",
            0,
            f"Queued for conversion: {asin} -> {format}",
        )

    async def queue_sync(
        self,
        job_id: UUID,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> None:
        """
        Queue a library sync job.

        Args:
            job_id: Unique job identifier.
            progress_callback: Optional callback for progress updates.
        """
        logger.info("Queuing library sync job %s", job_id)

        if progress_callback:
            self._progress_callbacks[job_id] = progress_callback

        task = asyncio.create_task(
            self._execute_sync(job_id),
            name=f"sync-{job_id}",
        )
        self._tasks[job_id] = task

        await self._notify_status(
            job_id,
            "QUEUED",
            0,
            "Queued for library sync",
        )

    async def queue_repair(
        self,
        job_id: UUID,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> None:
        """
        Queue a repair job (reconcile DB with manifests + filesystem).

        Args:
            job_id: Unique job identifier.
            progress_callback: Optional callback for progress updates.
        """
        logger.info("Queuing repair job %s", job_id)

        if progress_callback:
            self._progress_callbacks[job_id] = progress_callback

        task = asyncio.create_task(
            self._execute_repair(job_id),
            name=f"repair-{job_id}",
        )
        self._tasks[job_id] = task

        await self._notify_status(
            job_id,
            "QUEUED",
            0,
            "Queued for repair",
        )

    async def cancel_job(self, job_id: UUID) -> bool:
        """
        Cancel a running job.

        Args:
            job_id: Job to cancel.

        Returns:
            True if job was cancelled, False if not found.
        """
        if job_id in self._tasks:
            logger.info("Cancelling job %s", job_id)
            self._cancelled.add(job_id)
            self._tasks[job_id].cancel()
            try:
                await self._tasks[job_id]
            except asyncio.CancelledError:
                pass
            del self._tasks[job_id]
            self._cancelled.discard(job_id)
            if job_id in self._progress_callbacks:
                del self._progress_callbacks[job_id]

            await self._notify_status(
                job_id,
                "CANCELLED",
                0,
                "Job cancelled by user",
            )

            logger.info("Job %s cancelled successfully", job_id)
            return True

        logger.warning("Attempted to cancel non-existent job %s", job_id)
        return False

    def is_cancelled(self, job_id: UUID) -> bool:
        """Check if a job has been cancelled."""
        return job_id in self._cancelled

    def get_running_count(self) -> dict[str, int]:
        """Get count of running jobs by type."""
        downloads = sum(1 for t in self._tasks.values() if t.get_name().startswith("download-"))
        conversions = sum(1 for t in self._tasks.values() if t.get_name().startswith("convert-"))
        return {
            "downloads": downloads,
            "conversions": conversions,
            "total": downloads + conversions,
        }

    async def _execute_download(
        self,
        job_id: UUID,
        asins: list[str],
    ) -> dict[str, Any]:
        """
        Execute download with semaphore.

        Args:
            job_id: The job identifier.
            asins: List of ASINs to download.

        Returns:
            Dictionary with success status and results.
        """
        async with self.download_semaphore:
            logger.info("Starting download execution for job %s", job_id)

            if self.is_cancelled(job_id):
                logger.info("Job %s was cancelled before starting", job_id)
                return {"success": False, "cancelled": True}

            await self._notify_status(job_id, "RUNNING", 0, "Starting download")

            callback = self._progress_callbacks.get(job_id)
            results: list[dict[str, Any]] = []
            total = len(asins)

            for idx, asin in enumerate(asins):
                if self.is_cancelled(job_id):
                    logger.info("Job %s cancelled during download", job_id)
                    break

                progress = int((idx / total) * 100)
                message = f"Downloading {asin} ({idx + 1}/{total})"

                if callback:
                    callback(progress, message)

                await self._notify_status(job_id, "RUNNING", progress, message)

                try:
                    result = await self.audible_client.download(
                        asin=asin,
                        output_dir=self.settings.downloads_dir,
                        cover_size="1215",
                    )
                    results.append(result)

                    if not result.get("success"):
                        logger.warning(
                            "Download failed for ASIN %s in job %s",
                            asin,
                            job_id,
                        )
                except Exception as e:
                    logger.exception(
                        "Exception downloading ASIN %s in job %s",
                        asin,
                        job_id,
                    )
                    results.append({"success": False, "asin": asin, "error": str(e)})

            # Final status
            success = all(r.get("success", False) for r in results)
            successful_count = sum(1 for r in results if r.get("success"))

            if callback:
                callback(100, "Download complete")

            if success:
                await self._notify_status(
                    job_id,
                    "COMPLETED",
                    100,
                    f"Downloaded {successful_count}/{total} items",
                )
                logger.info("Download job %s completed successfully", job_id)

                # Update local paths in database
                async for session in get_session():
                    for res in results:
                        if res.get("success"):
                            asin = res.get("asin")
                            output_dir = Path(res.get("output_dir"))
                            
                            # Find files
                            files = res.get("files", [])
                            local_aax = next((f for f in files if f.endswith(".aax") or f.endswith(".aaxc")), None)
                            local_voucher = next((f for f in files if f.endswith(".voucher")), None)
                            local_cover = next((f for f in files if f.endswith(".jpg") or f.endswith(".png")), None)

                            # Update DB
                            stmt = select(Book).where(Book.asin == asin)
                            result = await session.execute(stmt)
                            book = result.scalar_one_or_none()
                            
                            if book:
                                if local_aax: book.local_path_aax = str(local_aax)
                                if local_voucher: book.local_path_voucher = str(local_voucher)
                                if local_cover: book.local_path_cover = str(local_cover)
                                book.status = BookStatus.DOWNLOADED
                                session.add(book)
                    
                    await session.commit()

            else:
                await self._notify_status(
                    job_id,
                    "COMPLETED",  # Still completed, but with failures
                    100,
                    f"Downloaded {successful_count}/{total} items (some failed)",
                )
                logger.warning(
                    "Download job %s completed with failures: %d/%d succeeded",
                    job_id,
                    successful_count,
                    total,
                )

            return {
                "success": success,
                "results": results,
                "successful_count": successful_count,
                "total_count": total,
            }

    async def _execute_sync(self, job_id: UUID) -> dict[str, Any]:
        """
        Execute library sync from Audible.
        """
        logger.info("Starting library sync execution for job %s", job_id)

        if self.is_cancelled(job_id):
            return {"success": False, "cancelled": True}

        await self._notify_status(job_id, "RUNNING", 0, "Connecting to Audible...")

        callback = self._progress_callbacks.get(job_id)

        try:
            # Check authentication
            if not await self.audible_client.is_authenticated():
                error_msg = "Not authenticated with Audible"
                await self._notify_status(job_id, "FAILED", 0, error=error_msg)
                return {"success": False, "error": error_msg}

            # Fetch library
            await self._notify_status(job_id, "RUNNING", 10, "Fetching library items...")
            library_items = await self.audible_client.get_library()
            total_items = len(library_items)
            
            await self._notify_status(
                job_id, "RUNNING", 20, f"Processing {total_items} items..."
            )

            # Update DB
            async for session in get_session():
                for idx, item in enumerate(library_items):
                    if self.is_cancelled(job_id):
                        break

                    asin = item.get("asin")
                    if not asin:
                        continue

                    # Update progress every 10 items
                    if idx % 10 == 0:
                        progress = 20 + int((idx / total_items) * 70)
                        msg = f"Syncing: {idx}/{total_items} items"
                        if callback:
                            callback(progress, msg)
                        await self._notify_status(job_id, "RUNNING", progress, msg)

                    # Check if book exists
                    stmt = select(Book).where(Book.asin == asin)
                    res = await session.execute(stmt)
                    existing_book = res.scalar_one_or_none()

                    # Normalize common fields (API returns dict/list; older sources may return strings)
                    authors_val = item.get("authors", [])
                    narrators_val = item.get("narrators", [])
                    series_val = item.get("series")

                    product_images_val: Any = item.get("product_images") or item.get("cover_url") or item.get(
                        "image_url"
                    )
                    if isinstance(product_images_val, str) and product_images_val.strip():
                        product_images_val = {
                            "500": product_images_val.strip(),
                            "250": product_images_val.strip(),
                        }

                    authors_json = json.dumps(authors_val, ensure_ascii=False)
                    narrators_json = json.dumps(narrators_val, ensure_ascii=False)
                    series_json = json.dumps(series_val, ensure_ascii=False) if series_val else None
                    product_images_json = (
                        json.dumps(product_images_val, ensure_ascii=False) if product_images_val else None
                    )

                    runtime_val = item.get("runtime_length_min")
                    runtime_length_min: int | None
                    if runtime_val is None:
                        runtime_length_min = None
                    elif isinstance(runtime_val, bool):
                        runtime_length_min = None
                    elif isinstance(runtime_val, int):
                        runtime_length_min = runtime_val
                    elif isinstance(runtime_val, str) and runtime_val.strip().isdigit():
                        runtime_length_min = int(runtime_val.strip())
                    else:
                        runtime_length_min = None

                    if existing_book:
                        existing_book.updated_at = datetime.utcnow()
                        existing_book.metadata_json = item
                        existing_book.title = item.get("title", existing_book.title)
                        existing_book.subtitle = item.get("subtitle")
                        existing_book.authors_json = authors_json
                        existing_book.narrators_json = narrators_json
                        existing_book.series_json = series_json
                        if runtime_length_min is not None:
                            existing_book.runtime_length_min = runtime_length_min
                        existing_book.release_date = item.get("release_date")
                        existing_book.purchase_date = item.get("purchase_date")
                        existing_book.product_images_json = product_images_json
                        existing_book.publisher = item.get("publisher_name")
                        existing_book.language = item.get("language")
                        existing_book.format_type = item.get("format_type")
                        existing_book.aax_available = item.get(
                            "aax_available", existing_book.aax_available
                        )
                        existing_book.aaxc_available = item.get(
                            "aaxc_available", existing_book.aaxc_available
                        )
                    else:
                        book = Book(
                            asin=asin,
                            title=item.get("title", "Unknown"),
                            subtitle=item.get("subtitle"),
                            authors_json=authors_json,
                            narrators_json=narrators_json,
                            series_json=series_json,
                            runtime_length_min=runtime_length_min or 0,
                            release_date=item.get("release_date"),
                            purchase_date=item.get("purchase_date"),
                            product_images_json=product_images_json,
                            metadata_json=item,
                            publisher=item.get("publisher_name"),
                            language=item.get("language"),
                            format_type=item.get("format_type"),
                            aax_available=item.get("aax_available", False),
                            aaxc_available=item.get("aaxc_available", False),
                            status=BookStatus.NEW,
                        )
                        session.add(book)

                await session.commit()
                break

            if self.is_cancelled(job_id):
                return {"success": False, "cancelled": True}

            await self._notify_status(job_id, "COMPLETED", 100, "Library sync complete")
            return {"success": True, "count": total_items}

        except Exception as e:
            logger.exception("Exception during sync job %s", job_id)
            await self._notify_status(job_id, "FAILED", 0, error=str(e))
            return {"success": False, "error": str(e)}

    async def _execute_repair(self, job_id: UUID) -> dict[str, Any]:
        """Execute repair pipeline (reconcile DB with manifests + filesystem)."""
        logger.info("Starting repair execution for job %s", job_id)

        if self.is_cancelled(job_id):
            return {"success": False, "cancelled": True}

        await self._notify_status(job_id, "RUNNING", 0, "Starting repair...")
        callback = self._progress_callbacks.get(job_id)

        try:
            async for session in get_session():
                if callback:
                    callback(20, "Reconciling manifests and filesystem...")
                await self._notify_status(job_id, "RUNNING", 20, "Reconciling manifests and filesystem...")
                result = await apply_repair(session)
                break

            await self._notify_status(
                job_id,
                "COMPLETED",
                100,
                f"Repair complete (updated_books={result.get('updated_books')}, inserted_local_items={result.get('inserted_local_items')})",
            )
            return {"success": True, **result}
        except Exception as e:
            logger.exception("Exception during repair job %s", job_id)
            await self._notify_status(job_id, "FAILED", 0, error=str(e))
            return {"success": False, "error": str(e)}

    async def _execute_conversion(
        self,
        job_id: UUID,
        asin: str,
        format: str,
        naming_scheme: str | None,
    ) -> dict[str, Any]:
        """
        Execute conversion with semaphore.

        Args:
            job_id: The job identifier.
            asin: ASIN of book to convert.
            format: Output format.
            naming_scheme: Optional naming scheme.

        Returns:
            Dictionary with conversion result.
        """
        async with self.convert_semaphore:
            logger.info("Starting conversion execution for job %s (ASIN: %s)", job_id, asin)

            if self.is_cancelled(job_id):
                logger.info("Job %s was cancelled before starting", job_id)
                return {"success": False, "cancelled": True}

            await self._notify_status(job_id, "RUNNING", 0, "Starting conversion")

            callback = self._progress_callbacks.get(job_id)

            # Find input file
            input_file = self._find_input_file(asin)
            if not input_file:
                error_msg = f"Input file not found for {asin}"
                logger.error(error_msg)
                if callback:
                    callback(-1, error_msg)
                await self._notify_status(job_id, "FAILED", 0, error=error_msg)
                return {"success": False, "error": "Input file not found"}

            logger.info("Found input file: %s", input_file)

            # Find voucher file for AAXC
            voucher_file = None
            if input_file.suffix.lower() == ".aaxc":
                voucher_file = input_file.with_suffix(".voucher")
                if not voucher_file.exists():
                    logger.warning("Voucher file not found for AAXC: %s", voucher_file)
                    voucher_file = None
                else:
                    logger.info("Using voucher file: %s", voucher_file)

            last_progress = 0

            def progress_wrapper(percent: int, line: str) -> None:
                nonlocal last_progress
                if callback:
                    callback(percent, line)

                # Also update via status callback for significant progress
                if percent >= 0 and percent > last_progress + 5:  # Every 5%
                    last_progress = percent
                    asyncio.create_task(
                        self._notify_status(
                            job_id,
                            "RUNNING",
                            percent,
                            f"Converting: {percent}%",
                        )
                    )

            try:
                result = await self.converter.convert(
                    input_file=input_file,
                    output_dir=self.settings.converted_dir,
                    format=format,
                    single_file=True,
                    voucher_file=voucher_file,
                    dir_naming_scheme=naming_scheme,
                    progress_callback=progress_wrapper,
                )

                if result.get("success"):
                    await self._notify_status(
                        job_id,
                        "COMPLETED",
                        100,
                        f"Conversion complete: {asin} -> {format}",
                    )
                    logger.info("Conversion job %s completed successfully", job_id)

                    # Update Book in DB
                    async for session in get_session():
                        try:
                            stmt = select(Book).where(Book.asin == asin)
                            db_res = await session.execute(stmt)
                            book = db_res.scalar_one_or_none()
                            if book:
                                book.status = BookStatus.COMPLETED
                                if "output_file" in result:
                                    book.local_path_converted = str(result["output_file"])
                                elif "files" in result and result["files"]:
                                    # Fallback if output_file is not set but files list is
                                    book.local_path_converted = str(result["files"][0])
                                
                                book.conversion_format = format
                                session.add(book)
                                await session.commit()
                        except Exception as e:
                            logger.error(f"Failed to update book status for {asin}: {e}")
                        finally:
                            break
                else:
                    error_msg = result.get("error") or result.get("stderr", "Unknown error")
                    await self._notify_status(
                        job_id,
                        "FAILED",
                        0,
                        error=str(error_msg)[:500],  # Truncate long errors
                    )
                    logger.error("Conversion job %s failed: %s", job_id, error_msg[:200])

                return result

            except Exception as e:
                logger.exception("Exception during conversion job %s", job_id)
                await self._notify_status(job_id, "FAILED", 0, error=str(e))
                return {"success": False, "error": str(e)}

    def _find_input_file(self, asin: str) -> Path | None:
        """Find downloaded AAX/AAXC file for an ASIN."""
        # Check downloads directory
        for ext in [".aaxc", ".aax"]:
            # Try with ASIN prefix
            for pattern in [f"{asin}*{ext}", f"*{asin}*{ext}"]:
                matches = list(self.settings.downloads_dir.glob(pattern))
                if matches:
                    return matches[0]

        # Check completed directory
        for ext in [".aaxc", ".aax"]:
            matches = list(self.settings.completed_dir.rglob(f"*{asin}*{ext}"))
            if matches:
                return matches[0]

        return None
