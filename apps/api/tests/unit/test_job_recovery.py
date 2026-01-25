"""Unit tests for job recovery routines."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from db.models import Job, JobStatus
from services.job_recovery import mark_inflight_jobs_interrupted


@pytest.mark.asyncio
async def test_mark_inflight_jobs_interrupted_marks_active_jobs_failed() -> None:
    running = Job(id=uuid4(), status=JobStatus.RUNNING, progress_percent=50)
    pending = Job(id=uuid4(), status=JobStatus.PENDING, progress_percent=0)
    queued = Job(id=uuid4(), status=JobStatus.QUEUED, progress_percent=10)
    paused = Job(id=uuid4(), status=JobStatus.PAUSED, progress_percent=20)

    session = AsyncMock()
    session.execute.return_value = MagicMock(
        scalars=lambda: MagicMock(all=lambda: [running, pending, queued, paused])
    )

    with patch("services.job_recovery.get_session") as mock_get_session:
        async def yield_session():
            yield session
        mock_get_session.side_effect = yield_session

        interrupted = await mark_inflight_jobs_interrupted()

    assert interrupted == 4
    for job in [running, pending, queued, paused]:
        assert job.status == JobStatus.FAILED
        assert job.completed_at is not None
        assert job.updated_at is not None
        assert job.error_message and "Interrupted by API restart" in job.error_message
        assert (job.progress_percent or 0) <= 99

    session.commit.assert_awaited_once()

