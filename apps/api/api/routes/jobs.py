"""Job management endpoints."""

import ast
import json
from datetime import datetime
from collections import deque
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Job, JobCreate, JobRead, JobStatus, JobType
from core.config import get_settings
from db.session import get_session
from services.job_manager import JobManager
from services.websocket_manager import WebSocketManager

router = APIRouter()

# Global managers (initialized on startup)
job_manager = JobManager()
ws_manager = WebSocketManager()


class JobCreateRequest(BaseModel):
    """Request body for creating a job."""

    asin: str | None = None
    asins: list[str] | None = None
    format: str | None = None
    naming_scheme: str | None = None


class JobCreateResponse(BaseModel):
    """Response for job creation."""

    job_id: UUID
    status: JobStatus
    message: str


class JobListResponse(BaseModel):
    """Response for job listing."""

    items: list[JobRead]
    total: int


class JobCancelResponse(BaseModel):
    """Response for job cancellation."""

    status: Literal["cancelled", "not_found", "already_completed"]
    message: str


class JobRetryResponse(BaseModel):
    """Response for retrying a job."""

    job_id: UUID
    status: JobStatus
    message: str


class JobHistoryClearResponse(BaseModel):
    """Response for clearing job history."""

    deleted: int
    message: str


class JobPauseResumeResponse(BaseModel):
    """Response for pausing/resuming a job."""

    status: Literal["paused", "resumed", "not_found", "not_active"]
    message: str


@router.get("", response_model=JobListResponse)
async def list_jobs(
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(
        default=None, 
        description="Filter by status. Can be comma-separated list, e.g. 'RUNNING,PENDING,QUEUED'"
    ),
    task_type: JobType | None = Query(default=None, description="Filter by task type"),
    limit: int = Query(default=50, ge=1, le=200),
) -> JobListResponse:
    """List jobs with optional filtering."""
    query = select(Job)
    count_query = select(func.count()).select_from(Job)

    if status:
        # Split by comma and filter empty strings
        status_list = [s.strip() for s in status.split(",") if s.strip()]
        if status_list:
            query = query.where(Job.status.in_(status_list))
            count_query = count_query.where(Job.status.in_(status_list))

    if task_type:
        query = query.where(Job.task_type == task_type)
        count_query = count_query.where(Job.task_type == task_type)

    query = query.order_by(Job.created_at.desc()).limit(limit)

    total_res = await session.execute(count_query)
    total = int(total_res.scalar_one() or 0)

    result = await session.execute(query)
    jobs = list(result.scalars().all())

    return JobListResponse(
        items=[JobRead.model_validate(job) for job in jobs],
        total=total,
    )


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Get a specific job by ID."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobRead.model_validate(job)


@router.post("/download", response_model=JobCreateResponse, status_code=202)
async def create_download_job(
    request: JobCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> JobCreateResponse:
    """Queue download job(s) for one or more ASINs.

    Uses a single job record for a batch download.
    """
    asins = request.asins or ([request.asin] if request.asin else [])

    if not asins:
        raise HTTPException(status_code=400, detail="At least one ASIN is required")

    payload: dict[str, Any] = {"asins": asins}
    job = Job(
        task_type=JobType.DOWNLOAD,
        book_asin=asins[0] if len(asins) == 1 else None,
        status=JobStatus.PENDING,
        payload_json=json.dumps(payload, ensure_ascii=False),
        updated_at=datetime.utcnow(),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    await job_manager.queue_download(job.id, asins)

    return JobCreateResponse(
        job_id=job.id,
        status=JobStatus.QUEUED,
        message=f"Download job queued for {len(asins)} item(s)",
    )


@router.post("/convert", response_model=JobCreateResponse, status_code=202)
async def create_convert_job(
    request: JobCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> JobCreateResponse:
    """Queue a conversion job for an ASIN."""
    if not request.asin:
        raise HTTPException(status_code=400, detail="ASIN is required for conversion")

    # Create job record
    payload: dict[str, Any] = {
        "asin": request.asin,
        "format": request.format or "m4b",
        "naming_scheme": request.naming_scheme,
    }

    job = Job(
        task_type=JobType.CONVERT,
        book_asin=request.asin,
        status=JobStatus.PENDING,
        payload_json=json.dumps(payload, ensure_ascii=False),
        updated_at=datetime.utcnow(),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Queue job for execution
    await job_manager.queue_conversion(
        job.id,
        request.asin,
        format=request.format or "m4b",
        naming_scheme=request.naming_scheme,
    )

    return JobCreateResponse(
        job_id=job.id,
        status=JobStatus.QUEUED,
        message=f"Conversion job queued for {request.asin}",
    )


@router.delete("/{job_id}", response_model=JobCancelResponse)
async def cancel_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> JobCancelResponse:
    """Cancel a pending or running job."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        return JobCancelResponse(
            status="not_found",
            message=f"Job {job_id} not found",
        )

    if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
        return JobCancelResponse(
            status="already_completed",
            message=f"Job {job_id} is already {job.status.value}",
        )

    # Cancel the job
    cancelled = await job_manager.cancel_job(job_id)

    if cancelled:
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        session.add(job)
        await session.commit()

        return JobCancelResponse(
            status="cancelled",
            message=f"Job {job_id} cancelled",
        )

    return JobCancelResponse(
        status="not_found",
        message=f"Job {job_id} could not be cancelled",
    )


@router.post("/{job_id}/pause", response_model=JobPauseResumeResponse)
async def pause_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> JobPauseResumeResponse:
    """Pause a pending/running job (cooperative; may not stop in-flight work)."""
    res = await session.execute(select(Job).where(Job.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        return JobPauseResumeResponse(status="not_found", message=f"Job {job_id} not found")

    if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
        return JobPauseResumeResponse(status="not_active", message=f"Job {job_id} is already {job.status.value}")

    ok = job_manager.pause_job(job_id)
    if not ok:
        return JobPauseResumeResponse(status="not_active", message=f"Job {job_id} is not running")

    now = datetime.utcnow()
    job.status = JobStatus.PAUSED
    job.status_message = "Paused by user"
    job.updated_at = now
    session.add(job)
    await session.commit()

    payload = {
        "type": "status",
        "job_id": str(job_id),
        "status": JobStatus.PAUSED.value,
        "progress": job.progress_percent,
        "message": job.status_message,
        "error": job.error_message,
        "updated_at": now.isoformat() + "Z",
    }
    await ws_manager.send_personal_message(payload, str(job_id))
    await ws_manager.send_personal_message(payload, "jobs")

    return JobPauseResumeResponse(status="paused", message=f"Job {job_id} paused")


@router.post("/{job_id}/resume", response_model=JobPauseResumeResponse)
async def resume_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> JobPauseResumeResponse:
    """Resume a paused job."""
    res = await session.execute(select(Job).where(Job.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        return JobPauseResumeResponse(status="not_found", message=f"Job {job_id} not found")

    if job.status != JobStatus.PAUSED:
        return JobPauseResumeResponse(status="not_active", message=f"Job {job_id} is not paused")

    ok = job_manager.resume_job(job_id)
    if not ok:
        return JobPauseResumeResponse(status="not_active", message=f"Job {job_id} cannot be resumed")

    now = datetime.utcnow()
    job.status = JobStatus.RUNNING
    job.status_message = "Resumed by user"
    job.updated_at = now
    session.add(job)
    await session.commit()

    payload = {
        "type": "status",
        "job_id": str(job_id),
        "status": JobStatus.RUNNING.value,
        "progress": job.progress_percent,
        "message": job.status_message,
        "error": job.error_message,
        "updated_at": now.isoformat() + "Z",
    }
    await ws_manager.send_personal_message(payload, str(job_id))
    await ws_manager.send_personal_message(payload, "jobs")

    return JobPauseResumeResponse(status="resumed", message=f"Job {job_id} resumed")


def _parse_payload(payload_json: str | None) -> dict[str, Any]:
    if not payload_json:
        return {}
    try:
        parsed = json.loads(payload_json)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        # Legacy format stored as str(dict). Use literal_eval as a safe fallback.
        try:
            parsed = ast.literal_eval(payload_json)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}


@router.post("/{job_id}/retry", response_model=JobRetryResponse, status_code=202)
async def retry_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> JobRetryResponse:
    """Retry a completed job by queuing a new job with the same payload."""
    res = await session.execute(select(Job).where(Job.id == job_id))
    job = res.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status in [JobStatus.RUNNING, JobStatus.PENDING, JobStatus.QUEUED]:
        raise HTTPException(status_code=409, detail="Job is still active")

    payload = _parse_payload(job.payload_json)
    now = datetime.utcnow()

    # Determine original job and attempt number for retry tracking
    original_id = job.original_job_id or job.id
    next_attempt = job.attempt + 1

    if job.task_type == JobType.DOWNLOAD:
        # Support both the current payload format ({asins:[...]})
        # and legacy format ({asin:"..."}).
        asins = payload.get("asins")
        if isinstance(asins, list) and asins:
            retry_asins = asins
        else:
            legacy_asin = payload.get("asin")
            retry_asins = [legacy_asin] if isinstance(legacy_asin, str) and legacy_asin else []

        if not retry_asins:
            raise HTTPException(status_code=400, detail="Download job has no ASINs to retry")

        new_payload: dict[str, Any] = {"asins": retry_asins}
        new_job = Job(
            task_type=JobType.DOWNLOAD,
            book_asin=retry_asins[0] if len(retry_asins) == 1 else None,
            status=JobStatus.PENDING,
            payload_json=json.dumps(new_payload, ensure_ascii=False),
            updated_at=now,
            attempt=next_attempt,
            original_job_id=original_id,
        )
        session.add(new_job)
        await session.commit()
        await session.refresh(new_job)

        await job_manager.queue_download(new_job.id, retry_asins)

        return JobRetryResponse(
            job_id=new_job.id,
            status=JobStatus.QUEUED,
            message=f"Retry download job queued for {len(retry_asins)} item(s) (attempt #{next_attempt})",
        )

    if job.task_type == JobType.CONVERT:
        asin = payload.get("asin")
        if not isinstance(asin, str) or not asin:
            raise HTTPException(status_code=400, detail="Convert job has no ASIN to retry")

        format_val = payload.get("format") or "m4b"
        naming_scheme = payload.get("naming_scheme")
        new_payload = {"asin": asin, "format": format_val, "naming_scheme": naming_scheme}
        new_job = Job(
            task_type=JobType.CONVERT,
            book_asin=asin,
            status=JobStatus.PENDING,
            payload_json=json.dumps(new_payload, ensure_ascii=False),
            updated_at=now,
            attempt=next_attempt,
            original_job_id=original_id,
        )
        session.add(new_job)
        await session.commit()
        await session.refresh(new_job)

        await job_manager.queue_conversion(
            new_job.id,
            asin,
            format=format_val,
            naming_scheme=naming_scheme,
        )

        return JobRetryResponse(
            job_id=new_job.id,
            status=JobStatus.QUEUED,
            message=f"Retry conversion job queued for {asin} (attempt #{next_attempt})",
        )

    raise HTTPException(status_code=400, detail=f"Retry not supported for job type {job.task_type.value}")


@router.delete("/history", response_model=JobHistoryClearResponse)
async def clear_job_history(
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(
        default="COMPLETED,FAILED,CANCELLED",
        description="Comma-separated statuses to delete (defaults to completed/failed/cancelled)",
    ),
    older_than: datetime | None = Query(default=None, description="Only delete jobs created before this time"),
    delete_logs: bool = Query(default=False, description="Also delete job log files on disk"),
) -> JobHistoryClearResponse:
    """Delete completed job history records (optionally deleting log files)."""
    status_list = [s.strip() for s in (status or "").split(",") if s.strip()]
    if not status_list:
        raise HTTPException(status_code=400, detail="At least one status is required")

    active = {JobStatus.RUNNING.value, JobStatus.PENDING.value, JobStatus.QUEUED.value}
    if any(s in active for s in status_list):
        raise HTTPException(status_code=400, detail="Cannot clear active job statuses")

    stmt = select(Job.id).where(Job.status.in_(status_list))
    if older_than:
        stmt = stmt.where(Job.created_at < older_than)

    res = await session.execute(stmt)
    ids = [row[0] for row in res.all()]
    if not ids:
        return JobHistoryClearResponse(deleted=0, message="No matching jobs to delete")

    await session.execute(delete(Job).where(Job.id.in_(ids)))
    await session.commit()

    if delete_logs:
        settings = get_settings()
        log_dir = settings.downloads_dir / ".job_logs"
        for job_id_val in ids:
            try:
                (log_dir / f"{job_id_val}.log").unlink(missing_ok=True)  # type: ignore[arg-type]
            except Exception:
                pass

    return JobHistoryClearResponse(deleted=len(ids), message=f"Deleted {len(ids)} job(s)")


@router.websocket("/ws/{job_id}")
async def job_websocket(
    websocket: WebSocket,
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """WebSocket endpoint for real-time job progress and logs."""
    # Verify job exists
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        await websocket.close(code=4004, reason="Job not found")
        return

    await ws_manager.connect(websocket, str(job_id))

    try:
        # Register a progress/log callback so the client receives "terminal" output.
        progress_cb = ws_manager.create_progress_callback(str(job_id))
        job_manager.set_progress_callback(job_id, progress_cb)

        # Send connected event + a human-friendly line so the log modal isn't empty.
        await ws_manager.send_personal_message(
            {
                "type": "connected",
                "job_id": str(job_id),
            },
            str(job_id),
        )

        # Replay tail of persisted logs (if present) so completed jobs show history.
        settings = get_settings()
        log_path = str(settings.downloads_dir / ".job_logs" / f"{job_id}.log")
        for line in _tail_lines(log_path, max_lines=500):
            await ws_manager.send_personal_message(
                {"type": "log", "job_id": str(job_id), "line": line},
                str(job_id),
            )

        # Send initial status
        await ws_manager.send_personal_message(
            {
                "type": "status",
                "job_id": str(job_id),
                "status": job.status.value,
                "progress": job.progress_percent,
                "message": job.status_message,
                "error": job.error_message,
                "updated_at": (job.updated_at.isoformat() + "Z") if getattr(job, "updated_at", None) else None,
            },
            str(job_id),
        )

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            # Handle ping/pong or other client messages
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        ws_manager.disconnect(websocket, str(job_id))
        job_manager.set_progress_callback(job_id, None)


@router.websocket("/ws")
async def jobs_websocket(
    websocket: WebSocket,
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Global jobs websocket feed.

    Used to avoid polling for RUNNING/PENDING/QUEUED job updates in the UI.
    """
    resource_id = "jobs"
    await ws_manager.connect(websocket, resource_id)

    try:
        # Send an initial snapshot of active jobs.
        stmt = (
            select(Job)
            .where(Job.status.in_([JobStatus.RUNNING, JobStatus.PENDING, JobStatus.QUEUED, JobStatus.PAUSED]))
            .order_by(Job.created_at.desc())
            .limit(200)
        )
        res = await session.execute(stmt)
        jobs = res.scalars().all()
        messages: list[dict[str, Any]] = []
        for job in jobs:
            messages.append(
                {
                    "type": "status",
                    "job_id": str(job.id),
                    "status": job.status.value,
                    "progress": job.progress_percent,
                    "message": job.status_message,
                    "error": job.error_message,
                    "updated_at": (job.updated_at.isoformat() + "Z") if getattr(job, "updated_at", None) else None,
                }
            )

        await ws_manager.send_personal_message(
            {"type": "batch", "messages": messages, "count": len(messages)},
            resource_id,
        )

        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket, resource_id)


async def handle_job_status_update(
    job_id: UUID,
    status: str,
    progress: int,
    message: str | None = None,
    error: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """
    Handle status updates from JobManager.
    Updates the database and broadcasts via WebSocket.
    """
    now = datetime.utcnow()
    now_iso = now.isoformat() + "Z"
    settings = get_settings()

    # Default values for WebSocket payload
    task_type: str | None = None
    book_asin: str | None = None
    attempt: int = 1
    original_job_id: str | None = None

    # Update Database first to get job metadata
    async for session in get_session():
        try:
            stmt = select(Job).where(Job.id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()

            if job:
                # Capture job metadata for WebSocket payload
                task_type = job.task_type.value if job.task_type else None
                book_asin = job.book_asin
                attempt = job.attempt or 1
                original_job_id = str(job.original_job_id) if job.original_job_id else None

                # Update job in database
                job.status = JobStatus(status)
                job.progress_percent = progress
                job.updated_at = now
                if message:
                    job.status_message = message
                if error:
                    job.error_message = error
                if not job.log_file_path:
                    job.log_file_path = str(settings.downloads_dir / ".job_logs" / f"{job_id}.log")

                if status == "RUNNING" and not job.started_at:
                    job.started_at = now

                if status in ["COMPLETED", "FAILED", "CANCELLED"]:
                    job.completed_at = now

                session.add(job)
                await session.commit()
        except Exception as e:
            # Log error but don't crash the job runner
            print(f"Error updating job status in DB: {e}")

        # Only need one session
        break

    # Broadcast via WebSocket (includes job metadata for proper frontend caching)
    payload = {
        "type": "status",
        "job_id": str(job_id),
        "status": status,
        "progress": progress,
        "message": message,
        "error": error,
        "meta": meta,
        "updated_at": now_iso,
        "task_type": task_type,
        "book_asin": book_asin,
        "attempt": attempt,
        "original_job_id": original_job_id,
    }

    # Send to specific job channel
    await ws_manager.send_personal_message(payload, str(job_id))
    # And to global jobs feed
    await ws_manager.send_personal_message(payload, "jobs")

    # Also emit log lines so the "View logs" UI has something to display.
    if message:
        await ws_manager.send_personal_message(
            {"type": "log", "line": f"{now_iso} [INFO] {message}"},
            str(job_id),
        )
    if error:
        await ws_manager.send_personal_message(
            {"type": "log", "line": f"{now_iso} [ERROR] {error}"},
            str(job_id),
        )

# Register the callback
job_manager.set_status_callback(handle_job_status_update)


def _tail_lines(path: str, max_lines: int = 500) -> list[str]:
    try:
        dq: deque[str] = deque(maxlen=max_lines)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                dq.append(line.rstrip("\n"))
        return list(dq)
    except Exception:
        return []
