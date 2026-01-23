"""Job recovery routines for process restarts."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from db.models import Job, JobStatus
from db.session import get_session


async def mark_inflight_jobs_interrupted() -> int:
    """
    Mark RUNNING/PENDING/QUEUED jobs as FAILED.

    Today, jobs are executed in-memory by JobManager. If the API process restarts,
    any in-flight jobs cannot continue and should be surfaced to the user as
    interrupted rather than appearing "stuck running forever".
    """
    now = datetime.utcnow()
    interrupted = 0

    async for session in get_session():
        stmt = select(Job).where(
            Job.status.in_([JobStatus.RUNNING, JobStatus.PENDING, JobStatus.QUEUED, JobStatus.PAUSED])
        )
        res = await session.execute(stmt)
        jobs = res.scalars().all()

        for job in jobs:
            job.status = JobStatus.FAILED
            job.progress_percent = min(job.progress_percent or 0, 99)
            job.error_message = (
                "Interrupted by API restart. Please retry or view logs for details."
            )
            job.completed_at = now
            job.updated_at = now
            session.add(job)
            interrupted += 1

        await session.commit()
        break

    return interrupted
