"""Async job manager with semaphore-based concurrency control."""

import asyncio
import json
import logging
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from core.config import get_settings
from db.models import Book, BookStatus, Job
from db.session import get_session
from services.audible_client import AudibleClient
from services.converter_engine import ConverterEngine
from services.metadata_extractor import MetadataExtractor
from services.library_manager import LibraryManager
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
        self._pause_events: dict[UUID, asyncio.Event] = {}

        # Progress callbacks per job
        self._progress_callbacks: dict[UUID, Callable[[int, str], None]] = {}

        # Status update callback (for WebSocket integration)
        self._status_callback = status_callback

        # Services
        self.audible_client = AudibleClient()
        self.converter = ConverterEngine()
        self.metadata_extractor = MetadataExtractor()
        self.library_manager = LibraryManager(self.metadata_extractor)
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

    def set_progress_callback(
        self, job_id: UUID, callback: Callable[[int, str], None] | None
    ) -> None:
        """Register (or clear) a per-job progress/log callback."""
        if callback is None:
            self._progress_callbacks.pop(job_id, None)
        else:
            self._progress_callbacks[job_id] = callback

    def _ensure_pause_event(self, job_id: UUID) -> asyncio.Event:
        ev = self._pause_events.get(job_id)
        if ev is None:
            ev = asyncio.Event()
            ev.set()
            self._pause_events[job_id] = ev
        return ev

    async def _wait_if_paused(self, job_id: UUID) -> None:
        ev = self._ensure_pause_event(job_id)
        await ev.wait()

    def pause_job(self, job_id: UUID) -> bool:
        """Pause a running job cooperatively (may not stop an in-flight subprocess)."""
        if job_id not in self._tasks:
            return False
        ev = self._ensure_pause_event(job_id)
        ev.clear()
        return True

    def resume_job(self, job_id: UUID) -> bool:
        """Resume a paused job."""
        if job_id not in self._tasks:
            return False
        ev = self._ensure_pause_event(job_id)
        ev.set()
        return True

    def _job_log_dir(self) -> Path:
        d = self.settings.data_dir / "job_logs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _job_log_path(self, job_id: UUID) -> Path:
        return self._job_log_dir() / f"{job_id}.log"

    def _format_log_line(self, level: str, line: str) -> str:
        ts = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
        safe = (line or "").rstrip("\n")
        return f"{ts} [{level}] {safe}"

    def _append_job_log(self, job_id: UUID, level: str, line: str) -> str:
        """
        Append a line to the job log and return the formatted line.

        Best-effort: never raises.
        """
        formatted = self._format_log_line(level, line)
        try:
            path = self._job_log_path(job_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.open("a", encoding="utf-8").write(formatted + "\n")
        except Exception:
            pass
        return formatted

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
        if message:
            self._append_job_log(job_id, "INFO", message)
        if error:
            self._append_job_log(job_id, "ERROR", error)

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
        self._ensure_pause_event(job_id)

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
        self._ensure_pause_event(job_id)

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

    async def queue_library_scan(
        self,
        job_id: UUID,
        force: bool = False,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> None:
        """
        Queue a library-wide metadata scan job.
        """
        logger.info("Queuing library scan job %s (force=%s)", job_id, force)

        if progress_callback:
            self._progress_callbacks[job_id] = progress_callback

        task = asyncio.create_task(
            self._execute_library_scan(job_id, force),
            name=f"scan-{job_id}",
        )
        self._tasks[job_id] = task

        await self._notify_status(
            job_id,
            "QUEUED",
            0,
            "Queued for library metadata scan",
        )

    async def _execute_library_scan(self, job_id: UUID, force: bool) -> dict[str, Any]:
        """Execute library scan with status updates."""
        logger.info("Starting library scan execution for job %s", job_id)
        await self._notify_status(job_id, "RUNNING", 0, "Starting metadata scan...")
        
        try:
            async for session in get_session():
                count = await self.library_manager.scan_library(session, force=force)
                break
            
            await self._notify_status(job_id, "COMPLETED", 100, f"Scan complete. Updated {count} books.")
            return {"success": True, "count": count}
        except Exception as e:
            logger.exception("Exception during library scan job %s", job_id)
            await self._notify_status(job_id, "FAILED", 0, error=str(e))
            return {"success": False, "error": str(e)}

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

            await self._wait_if_paused(job_id)
            await self._notify_status(job_id, "RUNNING", 0, "Starting download")

            # Pre-fetch book titles for better progress messages
            titles: dict[str, str] = {}
            try:
                async for session in get_session():
                    stmt = select(Book).where(Book.asin.in_(asins))
                    result = await session.execute(stmt)
                    books = result.scalars().all()
                    titles = {book.asin: book.title for book in books}
                    break
            except Exception as e:
                logger.warning("Could not fetch book titles: %s", e)

            callback = self._progress_callbacks.get(job_id)
            results: list[dict[str, Any]] = []
            total = len(asins)
            completed_count = 0
            results_lock = asyncio.Lock()

            # Semaphore to limit parallel downloads to 5
            download_limit = asyncio.Semaphore(5)

            async def download_one(asin: str) -> dict[str, Any]:
                nonlocal completed_count
                title = titles.get(asin, asin)

                async with download_limit:
                    await self._wait_if_paused(job_id)
                    if self.is_cancelled(job_id):
                        return {"success": False, "asin": asin, "cancelled": True}

                    # Log start
                    formatted = self._append_job_log(job_id, "INFO", f"Downloading: {title}")
                    if callback:
                        callback(-1, formatted)

                    try:
                        result = await self.audible_client.download(
                            asin=asin,
                            output_dir=self.settings.downloads_dir,
                            cover_size="1215",
                        )

                        async with results_lock:
                            completed_count += 1
                            progress = int((completed_count / total) * 100)
                            message = f"Downloading: {completed_count}/{total} completed"
                            await self._notify_status(job_id, "RUNNING", progress, message)
                            if callback:
                                callback(progress, message)

                        if not result.get("success"):
                            error_msg = result.get("stderr") or result.get("error") or "Unknown error"
                            error_log = f"Failed: {title} - {error_msg[:400]}"
                            logger.warning(
                                "Download failed for ASIN %s in job %s: %s",
                                asin,
                                job_id,
                                error_msg[:200],
                            )
                            formatted = self._append_job_log(job_id, "ERROR", error_log)
                            if callback:
                                callback(-1, formatted)
                        else:
                            formatted = self._append_job_log(job_id, "INFO", f"Completed: {title}")
                            if callback:
                                callback(-1, formatted)

                        return result

                    except Exception as e:
                        logger.exception(
                            "Exception downloading ASIN %s in job %s",
                            asin,
                            job_id,
                        )
                        async with results_lock:
                            completed_count += 1
                        formatted = self._append_job_log(job_id, "ERROR", f"Exception {title}: {str(e)[:500]}")
                        if callback:
                            callback(-1, formatted)
                        return {"success": False, "asin": asin, "error": str(e)}

            # Run all downloads in parallel (limited by semaphore)
            tasks = [download_one(asin) for asin in asins]
            results = await asyncio.gather(*tasks)

            # Final status
            success = all(r.get("success", False) for r in results)
            successful_count = sum(1 for r in results if r.get("success"))
            failed_results = [r for r in results if not r.get("success", False)]
            failed_asins = [r.get("asin") for r in failed_results if r.get("asin")]

            if callback:
                callback(100, "Download complete")
                callback(-1, self._format_log_line("INFO", "Download complete"))

            # Persist a result summary for the UI/debugging.
            result_summary = {
                "task_type": "DOWNLOAD",
                "total": total,
                "successful": successful_count,
                "failed": len(failed_results),
                "failed_asins": failed_asins,
            }

            # Update local paths in database for successful items (even if some failed).
            async for session in get_session():
                # Store result_json on the job record.
                res_job = await session.execute(select(Job).where(Job.id == job_id))
                job_row = res_job.scalar_one_or_none()
                if job_row:
                    job_row.result_json = json.dumps(result_summary, ensure_ascii=False)
                    session.add(job_row)

                for res in results:
                    if res.get("success"):
                        asin = res.get("asin")
                        if not asin:
                            continue

                        # Find files
                        files = res.get("files", [])
                        local_aax = next((f for f in files if f.endswith(".aax") or f.endswith(".aaxc")), None)
                        local_voucher = next((f for f in files if f.endswith(".voucher")), None)
                        local_cover = next((f for f in files if f.endswith(".jpg") or f.endswith(".png")), None)

                        # Update DB
                        stmt = select(Book).where(Book.asin == asin)
                        result = await session.execute(stmt)
                        book = result.scalar_one_or_none()

                        # Get title from book record or result
                        book_title = (book.title if book else None) or res.get("title") or asin

                        # Update download manifest
                        self._update_download_manifest(
                            asin=asin,
                            title=book_title,
                            aaxc_path=local_aax,
                            voucher_path=local_voucher,
                            cover_path=local_cover,
                        )

                        if book:
                            if local_aax:
                                book.local_path_aax = str(local_aax)
                            if local_voucher:
                                book.local_path_voucher = str(local_voucher)
                            if local_cover:
                                book.local_path_cover = str(local_cover)
                            book.status = BookStatus.DOWNLOADED
                            session.add(book)

                await session.commit()
                break

            if success:
                await self._notify_status(
                    job_id,
                    "COMPLETED",
                    100,
                    f"Downloaded {successful_count}/{total} items",
                )
                logger.info("Download job %s completed successfully", job_id)
            else:
                await self._notify_status(
                    job_id,
                    "FAILED",
                    100,
                    f"Downloaded {successful_count}/{total} items (some failed)",
                    error=f"{len(failed_results)} item(s) failed. See logs for details.",
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
        if callback:
            callback(-1, self._format_log_line("INFO", "Starting library sync"))

        try:
            # Check authentication
            if not await self.audible_client.is_authenticated():
                error_msg = "Not authenticated with Audible"
                await self._notify_status(job_id, "FAILED", 0, error=error_msg)
                return {"success": False, "error": error_msg}

            # Fetch library
            await self._notify_status(job_id, "RUNNING", 10, "Fetching library items...")
            if callback:
                callback(-1, self._format_log_line("INFO", "Fetching library items..."))
            library_items = await self.audible_client.get_library()
            total_items = len(library_items)
            
            await self._notify_status(
                job_id, "RUNNING", 20, f"Processing {total_items} items..."
            )
            if callback:
                callback(-1, self._format_log_line("INFO", f"Processing {total_items} items..."))

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
            if callback:
                callback(-1, self._format_log_line("INFO", "Library sync complete"))
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
        if callback:
            callback(-1, self._format_log_line("INFO", "Starting repair..."))

        try:
            async for session in get_session():
                if callback:
                    callback(20, "Reconciling manifests and filesystem...")
                    callback(-1, self._format_log_line("INFO", "Reconciling manifests and filesystem..."))
                await self._notify_status(job_id, "RUNNING", 20, "Reconciling manifests and filesystem...")
                result = await apply_repair(session, job_id=job_id)
                break

            def emit_info(msg: str) -> None:
                formatted = self._append_job_log(job_id, "INFO", msg)
                if callback:
                    callback(-1, formatted)

            await self._notify_status(
                job_id,
                "COMPLETED",
                100,
                f"Repair complete (updated_books={result.get('updated_books')}, inserted_local_items={result.get('inserted_local_items')}, duplicate_asins={result.get('duplicate_asins')})",
            )
            emit_info(
                f"Repair summary: updated_books={result.get('updated_books')}, inserted_local_items={result.get('inserted_local_items')}, deduped_local_items={result.get('deduped_local_items')}, duplicate_asins={result.get('duplicate_asins')}"
            )

            breakdown = result.get("updates_breakdown") or {}
            if isinstance(breakdown, dict) and breakdown:
                parts = []
                for k in [
                    "set_local_path_aax",
                    "set_local_path_voucher",
                    "set_local_path_cover",
                    "set_local_path_converted",
                    "set_conversion_format",
                    "set_status_downloaded",
                    "set_status_completed",
                ]:
                    v = breakdown.get(k)
                    if isinstance(v, int) and v > 0:
                        parts.append(f"{k}={v}")
                if parts:
                    emit_info("Updates: " + ", ".join(parts))

            report_path = result.get("duplicates_report_path")
            if isinstance(report_path, str) and report_path:
                emit_info(f"Duplicates report: {report_path}")

            if int(result.get("updated_books") or 0) == 0 and int(result.get("inserted_local_items") or 0) == 0:
                emit_info("No DB changes needed.")
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

            await self._wait_if_paused(job_id)
            await self._notify_status(job_id, "RUNNING", 0, "Starting conversion")

            callback = self._progress_callbacks.get(job_id)

            # Find input file
            # 1. Try to find input file using DB info first
            input_file = None
            book_title = None
            
            try:
                async for session in get_session():
                    stmt = select(Book).where(Book.asin == asin)
                    result = await session.execute(stmt)
                    book = result.scalar_one_or_none()
                    if book:
                        book_title = book.title
                        if book.local_path_aax:
                            p = Path(book.local_path_aax)
                            if p.exists():
                                input_file = p
                                logger.info("Using local_path_aax from DB: %s", input_file)
                    break
            except Exception as e:
                logger.warning("Failed to fetch book info for %s: %s", asin, e)

            # 2. Fallback to standard search if not found in DB or file missing
            if not input_file:
                input_file = self._find_input_file(asin, title=book_title)

            if not input_file:
                error_msg = f"Input file not found for {asin}"
                logger.error(error_msg)
                if callback:
                    callback(-1, self._append_job_log(job_id, "ERROR", error_msg))
                await self._notify_status(job_id, "FAILED", 0, error=error_msg)
                return {"success": False, "error": "Input file not found"}

            logger.info("Found input file: %s", input_file)

            # Capture start time for manifest
            started_at = datetime.utcnow().isoformat()

            # Find voucher file for AAXC
            voucher_file = None
            if input_file.suffix.lower() == ".aaxc":
                voucher_file = input_file.with_suffix(".voucher")
                if not voucher_file.exists():
                    logger.warning("Voucher file not found for AAXC: %s", voucher_file)
                    voucher_file = None
                else:
                    logger.info("Using voucher file: %s", voucher_file)

                # Self-healing: Check for chapters.json
                # AAXtoMP3 expects Title-chapters.json. 
                # If filename has hyphens, it strips extension. If not, it relies on our fix.
                # Here we assume standard naming convention matching the .aaxc file.
                chapters_file = Path(str(input_file).replace(".aaxc", "-chapters.json"))
                if not chapters_file.exists():
                    logger.warning("Chapters file missing at %s", chapters_file)
                    
                    # 1. Try to find it in downloads if we are in completed
                    if self.settings.completed_dir in input_file.parents:
                        fallback = self.settings.downloads_dir / chapters_file.name
                        if fallback.exists():
                            logger.info("Found orphaned chapters file in downloads, rescuing to: %s", chapters_file)
                            try:
                                shutil.move(str(fallback), str(chapters_file))
                            except Exception as e:
                                logger.error("Failed to rescue chapters file: %s", e)
                    
                    # 2. If still missing (or rescue failed), try to extract from AAXC
                    if not chapters_file.exists():
                         logger.info("Attempting to extract chapters from AAXC file...")
                         if await self._extract_chapters_from_aax(input_file, chapters_file):
                             logger.info("Successfully extracted chapters to %s", chapters_file)
                         else:
                             logger.warning("Could not recover chapters file.")


            last_progress = 0

            def progress_wrapper(percent: int, line: str) -> None:
                nonlocal last_progress
                if percent < 0:
                    # Treat as log line.
                    if not line:
                        return
                    trimmed = line if len(line) <= 2000 else (line[:2000] + "…")
                    formatted = self._append_job_log(job_id, "INFO", trimmed)
                    if callback:
                        callback(-1, formatted)
                    return

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
                    chapters_file=chapters_file,
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
                                
                                # Find output path from multiple possible keys
                                output_path = None
                                for key in ["output_files", "files", "output_file"]:
                                    val = result.get(key)
                                    if isinstance(val, list) and len(val) > 0:
                                        output_path = str(val[0])
                                        break
                                    elif isinstance(val, str) and val:
                                        output_path = val
                                        break
                                
                                if output_path:
                                    book.local_path_converted = output_path
                                
                                book.conversion_format = format
                                session.add(book)
                                await session.commit()
                                
                                # Trigger metadata scan for the new file
                                try:
                                    await self.library_manager.scan_book(session, asin)
                                except Exception as e:
                                    logger.error(f"Post-conversion scan failed for {asin}: {e}")

                                # Update converted manifest
                                book_title = book.title if book else asin
                                self._update_converted_manifest(
                                    source_path=str(input_file),
                                    asin=asin,
                                    title=book_title,
                                    output_path=output_path,
                                    success=True,
                                    started_at=started_at,
                                )

                                # Move source files to completed directory
                                self._move_sources_to_completed(input_file, asin)

                        except Exception as e:
                            logger.error(f"Failed to update book status for {asin}: {e}")
                        finally:
                            break
                else:
                    # Priority for error message: detected_errors[0] > error > stderr > Unknown error
                    detected = result.get("detected_errors", [])
                    error_msg = (
                        (detected[0] if detected else None)
                        or result.get("error")
                        or result.get("stderr")
                        or "Unknown error"
                    )
                    await self._notify_status(
                        job_id,
                        "FAILED",
                        0,
                        error=str(error_msg)[:500],  # Truncate long errors
                    )
                    logger.error("Conversion job %s failed: %s", job_id, str(error_msg)[:200])

                    # Update Book status to FAILED
                    async for session in get_session():
                        try:
                            stmt = select(Book).where(Book.asin == asin)
                            db_res = await session.execute(stmt)
                            book = db_res.scalar_one_or_none()
                            if book:
                                book.status = BookStatus.FAILED
                                session.add(book)
                                await session.commit()
                        except Exception as e:
                            logger.error(f"Failed to update book status to FAILED for {asin}: {e}")
                        finally:
                            break

                    # Update converted manifest with failure
                    self._update_converted_manifest(
                        source_path=str(input_file),
                        asin=asin,
                        title=asin,  # Use ASIN as title since we don't have book info
                        output_path=None,
                        success=False,
                        started_at=started_at,
                        error=str(error_msg)[:500],
                    )

                return result

            except Exception as e:
                logger.exception("Exception during conversion job %s", job_id)
                await self._notify_status(job_id, "FAILED", 0, error=str(e))
                return {"success": False, "error": str(e)}

    async def _extract_chapters_from_aax(self, input_file: Path, output_json: Path) -> bool:
        """
        Extract chapter metadata from AAX/AAXC file using ffprobe.
        
        Args:
            input_file: Path to the audio file.
            output_json: Path to write the JSON metadata to.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Run ffprobe to get chapters
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_chapters",
                str(input_file)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error("ffprobe failed to extract chapters: %s", stderr.decode())
                return False
                
            try:
                data = json.loads(stdout.decode())
            except json.JSONDecodeError:
                logger.error("Failed to parse ffprobe output as JSON")
                return False

            chapters = data.get("chapters", [])
            
            if not chapters:
                logger.warning("No chapters found in file %s", input_file)
                return False
                
            normalized_chapters = []
            for ch in chapters:
                # ffprobe uses seconds in float for start_time/end_time.
                # ConverterEngine._fix_chapters expects:
                # title, and (start_offset_ms + length_ms) OR (start + length).
                
                start_ms = int(float(ch.get("start_time", 0)) * 1000)
                end_ms = int(float(ch.get("end_time", 0)) * 1000)
                length_ms = end_ms - start_ms
                
                # Try to get title from tags
                title = ch.get("tags", {}).get("title")
                # If title is empty or missing, generate one
                if not title:
                    title = f"Chapter {ch.get('id', 0) + 1}"
                
                normalized_chapters.append({
                    "title": title,
                    "start_offset_ms": start_ms,
                    "length_ms": length_ms
                })
                
            with open(output_json, "w", encoding="utf-8") as f:
                json.dump(normalized_chapters, f, indent=2)
                
            logger.info("Extracted %d chapters to %s", len(normalized_chapters), output_json)
            return True
            
        except Exception as e:
            logger.exception("Exception extracting chapters: %s", e)
            return False

    def _find_input_file(self, asin: str, title: str | None = None) -> Path | None:
        """Find downloaded AAX/AAXC file for an ASIN (or title fallback)."""
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
        
        # Fallback: Search by title if provided
        if title:
            logger.info("ASIN not found, trying fallback search by title: %s", title)
            # Basic sanitation for glob matching
            clean_title = title.replace("/", "_").replace(":", "_")
            
            # Check downloads directory (flat)
            for f in self.settings.downloads_dir.glob("*"):
                if f.suffix.lower() in [".aax", ".aaxc"]:
                    if clean_title in f.name:
                        logger.info("Found file by title in downloads: %s", f)
                        return f
            
            # Check completed directory (recursive)
            for f in self.settings.completed_dir.rglob("*"):
                if f.suffix.lower() in [".aax", ".aaxc"]:
                    if clean_title in f.name:
                        logger.info("Found file by title in completed: %s", f)
                        return f

        return None

    def _update_converted_manifest(
        self,
        source_path: str,
        asin: str,
        title: str,
        output_path: str | None,
        success: bool,
        started_at: str,
        error: str | None = None,
    ) -> None:
        """
        Update converted manifest after conversion attempt.

        Args:
            source_path: Path to the source AAXC file (used as key).
            asin: The book ASIN.
            title: The book title.
            output_path: Path to the converted file (for success).
            success: Whether conversion succeeded.
            started_at: ISO timestamp when conversion started.
            error: Error message (for failure).
        """
        manifest_path = self.settings.manifest_dir / "converted_manifest.json"

        # Read existing manifest or start fresh
        manifest: dict[str, dict[str, Any]] = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning(
                    "Corrupt converted manifest at %s, starting fresh",
                    manifest_path,
                )
                manifest = {}

        # Key is the source AAXC path (matching worker.py pattern)
        key = source_path

        if success:
            manifest[key] = {
                "status": "success",
                "asin": asin,
                "title": title,
                "output_path": output_path or "",
                "started_at": started_at,
                "ended_at": datetime.utcnow().isoformat(),
            }
        else:
            manifest[key] = {
                "status": "failed",
                "asin": asin,
                "title": title,
                "error": error or "Unknown error",
                "ended_at": datetime.utcnow().isoformat(),
            }

        # Ensure directory exists
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        # Write manifest back
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info(
            "Updated converted manifest for %s (status=%s)",
            asin,
            "success" if success else "failed",
        )

    def _move_sources_to_completed(self, aaxc_path: Path, asin: str) -> None:
        """
        Move source files to completed directory after successful conversion.

        Only executes if move_after_complete setting is True.

        Args:
            aaxc_path: Path to the AAXC file.
            asin: The book ASIN (for logging).
        """
        if not self.settings.move_after_complete:
            return

        # Ensure completed directory exists
        self.settings.completed_dir.mkdir(parents=True, exist_ok=True)

        # Files to move: AAXC, voucher, chapters.json, and cover
        files_to_move: list[Path] = [
            aaxc_path,
            aaxc_path.with_suffix(".voucher"),
            Path(str(aaxc_path).replace(".aaxc", "-chapters.json")),
        ]

        # Move each file if it exists
        for file_path in files_to_move:
            if file_path.exists():
                try:
                    dest = self.settings.completed_dir / file_path.name
                    shutil.move(str(file_path), str(dest))
                    logger.info("Moved %s to %s", file_path.name, self.settings.completed_dir)
                except Exception as e:
                    logger.warning("Failed to move %s: %s", file_path, e)

        # Move cover files (glob for {stem}*jpg in same directory)
        stem = aaxc_path.stem
        parent_dir = aaxc_path.parent
        for jpg_file in parent_dir.glob(f"{stem}*.jpg"):
            try:
                dest = self.settings.completed_dir / jpg_file.name
                shutil.move(str(jpg_file), str(dest))
                logger.info("Moved %s to %s", jpg_file.name, self.settings.completed_dir)
            except Exception as e:
                logger.warning("Failed to move cover %s: %s", jpg_file, e)

    def _update_download_manifest(
        self,
        asin: str,
        title: str,
        aaxc_path: str | None,
        voucher_path: str | None,
        cover_path: str | None,
    ) -> None:
        """
        Update download manifest after successful download.

        Args:
            asin: The book ASIN.
            title: The book title.
            aaxc_path: Path to the downloaded AAXC file.
            voucher_path: Path to the voucher file.
            cover_path: Path to the cover image.
        """
        manifest_path = self.settings.manifest_dir / "download_manifest.json"

        # Read existing manifest or start fresh
        manifest: dict[str, dict[str, str]] = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning(
                    "Corrupt download manifest at %s, starting fresh",
                    manifest_path,
                )
                manifest = {}

        # Add/update entry
        manifest[asin] = {
            "asin": asin,
            "title": title,
            "aaxc_path": aaxc_path or "",
            "voucher_path": voucher_path or "",
            "cover_path": cover_path or "",
            "downloaded_at": datetime.utcnow().isoformat(),
            "status": "success",
        }

        # Ensure directory exists
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        # Write manifest back
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info("Updated download manifest for ASIN %s", asin)
