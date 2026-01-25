"""Additional integration tests for jobs endpoints (pause/resume/history)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Job, JobStatus, JobType


@pytest.mark.asyncio
async def test_pause_and_resume_job_updates_db(
    client: AsyncClient,
    test_session: AsyncSession,
) -> None:
    job = Job(task_type=JobType.DOWNLOAD, status=JobStatus.RUNNING, progress_percent=12)
    test_session.add(job)
    await test_session.commit()
    await test_session.refresh(job)

    with patch("api.routes.jobs.job_manager") as mock_manager:
        mock_manager.pause_job.return_value = True
        mock_manager.resume_job.return_value = True
        mock_manager.set_progress_callback = lambda *_args, **_kwargs: None

        res = await client.post(f"/jobs/{job.id}/pause")
        assert res.status_code == 200
        assert res.json()["status"] == "paused"

        await test_session.refresh(job)
        assert job.status == JobStatus.PAUSED

        res = await client.post(f"/jobs/{job.id}/resume")
        assert res.status_code == 200
        assert res.json()["status"] == "resumed"

        await test_session.refresh(job)
        assert job.status == JobStatus.RUNNING


@pytest.mark.asyncio
async def test_clear_job_history_deletes_matching_jobs(
    client: AsyncClient,
    test_session: AsyncSession,
    tmp_path: Path,
) -> None:
    old = datetime.utcnow() - timedelta(days=2)
    completed = Job(task_type=JobType.DOWNLOAD, status=JobStatus.COMPLETED, created_at=old)
    failed = Job(task_type=JobType.CONVERT, status=JobStatus.FAILED, created_at=old)
    running = Job(task_type=JobType.SYNC, status=JobStatus.RUNNING, created_at=old)
    test_session.add_all([completed, failed, running])
    await test_session.commit()
    await test_session.refresh(completed)
    await test_session.refresh(failed)

    # Reject attempts to delete active statuses
    res = await client.delete("/jobs/history?status=RUNNING")
    assert res.status_code == 400

    # Create a log file and exercise delete_logs path.
    log_dir = tmp_path / ".job_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"{completed.id}.log").write_text("x\n", encoding="utf-8")

    with patch("api.routes.jobs.get_settings") as mock_settings:
        mock_settings.return_value = type("S", (), {"downloads_dir": tmp_path})()
        res = await client.delete("/jobs/history?older_than=2100-01-01T00:00:00&delete_logs=true")

    assert res.status_code == 200
    data = res.json()
    assert data["deleted"] >= 2

