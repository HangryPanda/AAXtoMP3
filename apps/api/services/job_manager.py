"""Async job manager with semaphore-based concurrency control."""

import asyncio
import json
import logging
import shutil
import re
import glob
import httpx
from collections.abc import Callable
from datetime import datetime
from time import monotonic
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
        meta: dict[str, Any] | None = None,
    ) -> None:
        """
        Called when job status changes.

        Args:
            job_id: The job identifier.
            status: New status string.
            progress: Progress percentage (0-100).
            message: Optional status message.
            error: Optional error message.
            meta: Optional structured metadata for UI (not logged).
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

        # Shutdown coordination
        self._shutdown_event = asyncio.Event()
        self._shutting_down = False

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
        # Persist logs on the same volume as downloads so container recreation
        # doesn't wipe job logs (dev/prod bind-mount `/data/downloads`).
        d = self.settings.downloads_dir / ".job_logs"
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
        meta: dict[str, Any] | None = None,
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
                    meta=meta,
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

    async def shutdown(self, timeout: float = 30.0) -> None:
        """
        Gracefully shutdown all running jobs.

        This method:
        1. Signals all jobs to stop accepting new work
        2. Cancels all running tasks
        3. Waits for tasks to complete (with timeout)
        4. Closes any open file handles

        Args:
            timeout: Maximum time to wait for jobs to complete (seconds).
        """
        if self._shutting_down:
            logger.warning("Shutdown already in progress")
            return

        self._shutting_down = True
        self._shutdown_event.set()

        running_count = len(self._tasks)
        if running_count == 0:
            logger.info("No running jobs to shutdown")
            return

        logger.info("Shutting down %d running job(s)...", running_count)

        # Mark all jobs as cancelled
        for job_id in list(self._tasks.keys()):
            self._cancelled.add(job_id)
            # Resume any paused jobs so they can exit
            ev = self._pause_events.get(job_id)
            if ev:
                ev.set()

        # Cancel all tasks
        for job_id, task in list(self._tasks.items()):
            if not task.done():
                logger.info("Cancelling job %s (%s)", job_id, task.get_name())
                task.cancel()

        # Wait for all tasks to complete with timeout
        if self._tasks:
            tasks = list(self._tasks.values())
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout,
                )
                logger.info("All jobs completed gracefully")
            except asyncio.TimeoutError:
                logger.warning(
                    "Timeout waiting for jobs to complete. %d job(s) still running.",
                    sum(1 for t in tasks if not t.done()),
                )

        # Clear internal state
        self._tasks.clear()
        self._cancelled.clear()
        self._pause_events.clear()
        self._progress_callbacks.clear()

        logger.info("Job manager shutdown complete")

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._shutting_down

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
        total = len(asins)
        completed_count = 0
        results_lock = asyncio.Lock()

        # Byte-level progress per ASIN: (current_bytes, total_bytes)
        progress_bytes: dict[str, tuple[int, int]] = {}
        progress_dirty = asyncio.Event()
        last_emit_at = 0.0
        last_emit_progress = -1

        async def _publish_progress_loop() -> None:
            nonlocal last_emit_at, last_emit_progress
            last_bytes_sum = 0
            last_bytes_at = monotonic()
            while True:
                await progress_dirty.wait()
                progress_dirty.clear()
                await self._wait_if_paused(job_id)
                if self.is_cancelled(job_id):
                    return

                now = monotonic()
                if now - last_emit_at < 0.5:
                    continue

                totals = [v for v in progress_bytes.values() if v[1] > 0]
                if totals:
                    cur_sum = sum(v[0] for v in totals)
                    tot_sum = sum(v[1] for v in totals)
                    pct = int((cur_sum / tot_sum) * 100) if tot_sum > 0 else 0
                else:
                    cur_sum = 0
                    tot_sum = 0
                    pct = int((completed_count / total) * 100) if total else 0

                if pct == last_emit_progress:
                    continue

                # Avoid spamming logs: keep status_message sparse, but always send meta for UI.
                message = f"Downloading: {completed_count}/{total} completed" if pct % 5 == 0 else None

                bytes_per_sec = 0.0
                dt = max(0.001, now - last_bytes_at)
                if cur_sum >= last_bytes_sum:
                    bytes_per_sec = (cur_sum - last_bytes_sum) / dt
                last_bytes_sum = cur_sum
                last_bytes_at = now

                meta = None
                if tot_sum > 0:
                    meta = {
                        "download_bytes_current": cur_sum,
                        "download_bytes_total": tot_sum,
                        "download_bytes_per_sec": bytes_per_sec,
                    }

                await self._notify_status(job_id, "RUNNING", pct, message, meta=meta)
                if callback and message:
                    callback(pct, message)

                last_emit_progress = pct
                last_emit_at = now

        progress_task = asyncio.create_task(_publish_progress_loop(), name=f"dl-progress-{job_id}")

        async def download_one(asin: str) -> dict[str, Any]:
            nonlocal completed_count
            title = titles.get(asin, asin)

            async with self.download_semaphore:
                await self._wait_if_paused(job_id)
                if self.is_cancelled(job_id):
                    return {"success": False, "asin": asin, "cancelled": True}

                formatted = self._append_job_log(job_id, "INFO", f"Downloading: {title}")
                if callback:
                    callback(-1, formatted)

                def _progress_cb(cur_b: int, tot_b: int) -> None:
                    if tot_b <= 0:
                        return
                    progress_bytes[asin] = (cur_b, tot_b)
                    progress_dirty.set()

                try:
                    result = await self.audible_client.download(
                        asin=asin,
                        output_dir=self.settings.downloads_dir,
                        cover_size="1215",
                        progress_callback=_progress_cb,
                    )

                    async with results_lock:
                        completed_count += 1
                        cur_tot = progress_bytes.get(asin)
                        if cur_tot and cur_tot[1] > 0:
                            progress_bytes[asin] = (cur_tot[1], cur_tot[1])
                        progress_dirty.set()

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
                    logger.exception("Exception downloading ASIN %s in job %s", asin, job_id)
                    async with results_lock:
                        completed_count += 1
                        progress_dirty.set()
                    formatted = self._append_job_log(job_id, "ERROR", f"Exception {title}: {str(e)[:500]}")
                    if callback:
                        callback(-1, formatted)
                    return {"success": False, "asin": asin, "error": str(e)}

        try:
            tasks = [asyncio.create_task(download_one(asin), name=f"download-one-{asin}") for asin in asins]
            results = await asyncio.gather(*tasks)
        finally:
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        success = all(r.get("success", False) for r in results)
        successful_count = sum(1 for r in results if r.get("success"))
        failed_results = [r for r in results if not r.get("success", False)]
        failed_asins = [r.get("asin") for r in failed_results if r.get("asin")]

        if callback:
            callback(100, "Download complete")
            callback(-1, self._format_log_line("INFO", "Download complete"))

        result_summary = {
            "task_type": "DOWNLOAD",
            "total": total,
            "successful": successful_count,
            "failed": len(failed_results),
            "failed_asins": failed_asins,
        }

        # Update local paths in database for successful items (even if some failed).
        async for session in get_session():
            res_job = await session.execute(select(Job).where(Job.id == job_id))
            job_row = res_job.scalar_one_or_none()
            if job_row:
                job_row.result_json = json.dumps(result_summary, ensure_ascii=False)
                session.add(job_row)

            for res in results:
                if not res.get("success"):
                    continue

                asin = res.get("asin")
                if not asin:
                    continue

                files = res.get("files", [])
                local_aax = next((f for f in files if f.endswith(".aax") or f.endswith(".aaxc")), None)
                local_voucher = next((f for f in files if f.endswith(".voucher")), None)
                local_cover = next((f for f in files if f.endswith(".jpg") or f.endswith(".png")), None)

                stmt = select(Book).where(Book.asin == asin)
                result = await session.execute(stmt)
                book = result.scalar_one_or_none()

                book_title = (book.title if book else None) or res.get("title") or asin

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
                        # Only mark as DOWNLOADED if we actually have the aaxc file
                        book.status = BookStatus.DOWNLOADED
                    if local_voucher:
                        book.local_path_voucher = str(local_voucher)
                    if local_cover:
                        book.local_path_cover = str(local_cover)
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
            error_detail: str | None = None
            if total == 1 and failed_results:
                r0 = failed_results[0]
                err0 = (r0.get("stderr") or r0.get("error") or "").strip()
                asin0 = r0.get("asin") or (asins[0] if asins else "")
                title0 = titles.get(str(asin0), str(asin0))
                if err0:
                    error_detail = f"Failed: {title0} - {err0[:400]}"

            await self._notify_status(
                job_id,
                "FAILED",
                100,
                f"Downloaded {successful_count}/{total} items (some failed)",
                error=error_detail or f"{len(failed_results)} item(s) failed. See logs for details.",
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

    def _make_conversion_progress_wrapper(
        self,
        job_id: UUID,
        callback: Callable[[int, str], None] | None,
    ) -> Callable[[int, str, dict[str, Any] | None], None]:
        """
        Create a conversion progress callback that:
        - Treats negative percent as log lines (job log + callback(-1, ...))
        - Emits sparse status messages (every 5%)
        - Emits structured conversion telemetry in status.meta (throttled to <= 2/sec)
        """
        last_message_progress = 0
        last_meta_time = 0.0
        meta_throttle_interval = 0.5  # 500ms = 2 updates/sec max

        def progress_wrapper(percent: int, line: str, telemetry: dict[str, Any] | None = None) -> None:
            nonlocal last_message_progress, last_meta_time

            if percent < 0:
                if not line:
                    return
                trimmed = line if len(line) <= 2000 else (line[:2000] + "…")
                formatted = self._append_job_log(job_id, "INFO", trimmed)
                if callback:
                    callback(-1, formatted)
                return

            if callback:
                callback(percent, line)

            significant_progress = percent >= last_message_progress + 5
            if significant_progress:
                last_message_progress = percent
                asyncio.create_task(
                    self._notify_status(
                        job_id,
                        "RUNNING",
                        percent,
                        f"Converting: {percent}%",
                        meta=None,
                    )
                )

            if telemetry is None:
                return

            meta: dict[str, Any] = {}
            for k in ["convert_current_ms", "convert_total_ms", "convert_speed_x", "convert_bitrate_kbps"]:
                if k in telemetry:
                    meta[k] = telemetry[k]
            if not meta:
                return

            now = monotonic()
            if now - last_meta_time < meta_throttle_interval:
                return
            last_meta_time = now

            asyncio.create_task(
                self._notify_status(
                    job_id,
                    "RUNNING",
                    percent,
                    message=None,
                    meta=meta,
                )
            )

        return progress_wrapper

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
                         if await self._extract_chapters_from_aax(input_file, chapters_file, asin):
                             logger.info("Successfully extracted chapters to %s", chapters_file)
                         else:
                             logger.warning("Could not recover chapters file.")

                # Self-healing: Check for cover art
                # AAXtoMP3 expects {stem}_{resolution}.jpg
                # We check for any jpg starting with the stem
                try:
                    cover_candidates = list(input_file.parent.glob(f"{glob.escape(input_file.stem)}_*.jpg"))
                    
                    # Try to rescue from downloads if not found and we are in completed
                    if not cover_candidates and self.settings.completed_dir in input_file.parents:
                         dl_candidates = list(self.settings.downloads_dir.glob(f"{glob.escape(input_file.stem)}_*.jpg"))
                         if dl_candidates:
                             for c in dl_candidates:
                                 try:
                                     shutil.copy(str(c), str(input_file.parent / c.name))
                                     cover_candidates.append(input_file.parent / c.name)
                                     logger.info("Rescued cover art from downloads: %s", c.name)
                                 except Exception:
                                     pass

                    if not cover_candidates:
                        logger.warning("Cover art missing for %s. Attempting to download...", input_file.name)
                        # Get book from DB to find URL
                        async for session in get_session():
                            stmt = select(Book).where(Book.asin == asin)
                            res = await session.execute(stmt)
                            book = res.scalar_one_or_none()
                            if book and book.product_images_json:
                                try:
                                    images = json.loads(book.product_images_json)
                                    if isinstance(images, dict):
                                        # Get highest res
                                        url = images.get("1215") or images.get("500") or list(images.values())[0]
                                        if url:
                                            # Save as _1215.jpg to match AAXtoMP3 expectation
                                            target_cover = input_file.parent / f"{input_file.stem}_1215.jpg"
                                            async with httpx.AsyncClient() as client:
                                                resp = await client.get(url, follow_redirects=True)
                                                if resp.status_code == 200:
                                                    target_cover.write_bytes(resp.content)
                                                    logger.info("Downloaded cover art to %s", target_cover)
                                                else:
                                                    logger.error("Failed to download cover: %s", resp.status_code)
                                except Exception as e:
                                    logger.error("Failed to parse image JSON or download: %s", e)
                            break
                except Exception as e:
                    logger.error("Error checking/rescuing cover art: %s", e)

            progress_wrapper = self._make_conversion_progress_wrapper(job_id, callback)

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
                    raw_error = (
                        (detected[0] if detected else None)
                        or result.get("error")
                        or result.get("stderr")
                        or "Unknown error"
                    )
                    
                    # Map to user-friendly error messages
                    friendly_error = raw_error
                    lower_err = str(raw_error).lower()
                    
                    if "file not found" in lower_err and "chapters.json" in lower_err:
                        friendly_error = "Missing metadata file (chapters.json). Please delete this book and re-download it to fix."
                    elif "cover file not found" in lower_err:
                        friendly_error = "Cover art file missing. Please delete this book and re-download it to fix."
                    elif "operation not permitted" in lower_err:
                        friendly_error = "Permission error moving file. The destination file might be locked or owned by another user."
                    elif "no output files generated" in lower_err:
                        friendly_error = "Conversion produced no files. Check logs for ffmpeg errors."
                    elif "duration mismatch" in lower_err:
                        friendly_error = "Integrity check failed: Output duration does not match input."

                    await self._notify_status(
                        job_id,
                        "FAILED",
                        0,
                        error=str(friendly_error)[:500],  # Truncate long errors
                    )
                    logger.error("Conversion job %s failed: %s", job_id, str(raw_error)[:200])

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
                        error=str(raw_error)[:500],
                    )

                return result

            except Exception as e:
                logger.exception("Exception during conversion job %s", job_id)
                await self._notify_status(job_id, "FAILED", 0, error=str(e))
                return {"success": False, "error": str(e)}

    async def _extract_chapters_from_aax(self, input_file: Path, output_json: Path, asin: str | None = None) -> bool:
        """
        Extract chapter metadata from AAX/AAXC file using ffprobe.
        
        Args:
            input_file: Path to the audio file.
            output_json: Path to write the JSON metadata to.
            asin: ASIN of the book (optional, for metadata).
            
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
            
            # Wrap in audible-cli structure required by AAXtoMP3
            wrapper = {
                "content_metadata": {
                    "chapter_info": {
                        "chapters": normalized_chapters
                    },
                    "content_reference": {
                        "asin": asin or ""
                    }
                }
            }
                
            with open(output_json, "w", encoding="utf-8") as f:
                json.dump(wrapper, f, indent=2)
                
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
        Update download manifest after download attempt.

        Status is set based on what was actually downloaded:
        - "success": AAXC file was downloaded (conversion-ready)
        - "partial": Only cover/voucher downloaded (needs re-download)

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
        # Only mark as "success" if the aaxc file was actually downloaded.
        # If only cover/voucher downloaded, mark as "partial" so conversion won't be attempted.
        status = "success" if aaxc_path else "partial"
        if status == "partial":
            logger.warning(
                "Partial download for ASIN %s: no AAXC file downloaded (cover_path=%s)",
                asin,
                cover_path,
            )
        manifest[asin] = {
            "asin": asin,
            "title": title,
            "aaxc_path": aaxc_path or "",
            "voucher_path": voucher_path or "",
            "cover_path": cover_path or "",
            "downloaded_at": datetime.utcnow().isoformat(),
            "status": status,
        }

        # Ensure directory exists
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        # Write manifest back
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info("Updated download manifest for ASIN %s", asin)
