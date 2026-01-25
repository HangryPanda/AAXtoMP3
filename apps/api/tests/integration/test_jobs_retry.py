"""Integration tests for /jobs/{job_id}/retry."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from db.models import Job, JobStatus, JobType


@pytest.mark.asyncio
async def test_retry_download_job_supports_legacy_payload_asin(
    client: AsyncClient,
    test_session,
) -> None:
    """Legacy payload_json {\"asin\": ...} can be retried."""
    job = Job(
        task_type=JobType.DOWNLOAD,
        book_asin="B09RX4LQTL",
        status=JobStatus.FAILED,
        payload_json=json.dumps({"asin": "B09RX4LQTL"}),
        updated_at=datetime.utcnow(),
    )
    test_session.add(job)
    await test_session.commit()
    await test_session.refresh(job)

    with patch("api.routes.jobs.job_manager") as mock_manager:
        mock_manager.queue_download = AsyncMock()
        res = await client.post(f"/jobs/{job.id}/retry")

    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "QUEUED"
    mock_manager.queue_download.assert_called_once()
    queued_asins = mock_manager.queue_download.call_args.args[1]
    assert queued_asins == ["B09RX4LQTL"]


@pytest.mark.asyncio
async def test_retry_download_job_uses_asins_payload(
    client: AsyncClient,
    test_session,
) -> None:
    """Current payload_json {\"asins\": [...]} is retried as-is."""
    job = Job(
        task_type=JobType.DOWNLOAD,
        book_asin=None,
        status=JobStatus.FAILED,
        payload_json=json.dumps({"asins": ["0063137321"]}),
        updated_at=datetime.utcnow(),
    )
    test_session.add(job)
    await test_session.commit()
    await test_session.refresh(job)

    with patch("api.routes.jobs.job_manager") as mock_manager:
        mock_manager.queue_download = AsyncMock()
        res = await client.post(f"/jobs/{job.id}/retry")

    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "QUEUED"
    mock_manager.queue_download.assert_called_once()
    queued_asins = mock_manager.queue_download.call_args.args[1]
    assert queued_asins == ["0063137321"]

