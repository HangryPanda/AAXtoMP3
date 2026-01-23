"""Job management endpoints."""

from datetime import datetime
from collections import deque
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
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
    query = select(Job).order_by(Job.created_at.desc())

    if status:
        # Split by comma and filter empty strings
        status_list = [s.strip() for s in status.split(",") if s.strip()]
        if status_list:
            query = query.where(Job.status.in_(status_list))

    if task_type:
        query = query.where(Job.task_type == task_type)

    query = query.limit(limit)

    result = await session.execute(query)
    jobs = result.scalars().all()

    return JobListResponse(
        items=[JobRead.model_validate(job) for job in jobs],
        total=len(jobs),
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
    """Queue a download job for one or more ASINs."""
    asins = request.asins or ([request.asin] if request.asin else [])

    if not asins:
        raise HTTPException(status_code=400, detail="At least one ASIN is required")

    # Create job record
    payload: dict[str, Any] = {"asins": asins}

    job = Job(
        task_type=JobType.DOWNLOAD,
        book_asin=asins[0] if len(asins) == 1 else None,
        status=JobStatus.PENDING,
        payload_json=str(payload),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Queue job for execution
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
        payload_json=str(payload),
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
        log_path = str(settings.data_dir / "job_logs" / f"{job_id}.log")
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
            .where(Job.status.in_([JobStatus.RUNNING, JobStatus.PENDING, JobStatus.QUEUED]))
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
                    "message": None,
                    "error": job.error_message,
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
) -> None:
    """
    Handle status updates from JobManager.
    Updates the database and broadcasts via WebSocket.
    """
    # 1. Broadcast via WebSocket
    payload = {
        "type": "status",
        "job_id": str(job_id),
        "status": status,
        "progress": progress,
        "message": message,
        "error": error,
    }
    
    # Send to specific job channel
    await ws_manager.send_personal_message(payload, str(job_id))
    # And to global jobs feed
    await ws_manager.send_personal_message(payload, "jobs")

    # Also emit log lines so the "View logs" UI has something to display.
    now_iso = datetime.utcnow().isoformat() + "Z"
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

    # 2. Update Database
    # We need to manually manage the session here since we're outside a request context
    async for session in get_session():
        try:
            stmt = select(Job).where(Job.id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()

            if job:
                job.status = JobStatus(status)
                job.progress_percent = progress
                if message:
                    # We might want to store the last message or append to logs
                    # For now, let's just update error if present
                    pass
                if error:
                    job.error_message = error
                
                if status == "RUNNING" and not job.started_at:
                    job.started_at = datetime.utcnow()
                
                if status in ["COMPLETED", "FAILED", "CANCELLED"]:
                    job.completed_at = datetime.utcnow()
                
                session.add(job)
                await session.commit()
        except Exception as e:
            # Log error but don't crash the job runner
            print(f"Error updating job status in DB: {e}")
        
        # Only need one session
        break

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
