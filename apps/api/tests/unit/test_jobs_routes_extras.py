"""Unit tests for jobs route helpers and websocket handlers."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import WebSocketDisconnect

from db.models import Job, JobStatus, JobType


@pytest.mark.asyncio
async def test_handle_job_status_update_updates_db_and_broadcasts(tmp_path: Path) -> None:
    from api.routes import jobs as jobs_routes

    job_id = uuid4()
    job = Job(id=job_id, task_type=JobType.DOWNLOAD, status=JobStatus.PENDING, progress_percent=0)

    session = AsyncMock()
    session.execute.return_value = MagicMock(scalar_one_or_none=lambda: job)

    settings = MagicMock()
    settings.downloads_dir = tmp_path

    with patch.object(jobs_routes, "get_settings", return_value=settings), patch.object(
        jobs_routes, "get_session"
    ) as mock_get_session, patch.object(jobs_routes.ws_manager, "send_personal_message", AsyncMock()) as spm:
        async def yield_session():
            yield session
        mock_get_session.side_effect = yield_session

        await jobs_routes.handle_job_status_update(
            job_id,
            "RUNNING",
            10,
            message="hello",
            error="oops",
            meta={"k": "v"},
        )

    session.commit.assert_awaited_once()
    assert job.status == JobStatus.RUNNING
    assert job.progress_percent == 10
    # Status broadcast to job channel and global jobs channel (+ 2 log messages)
    assert spm.await_count >= 4


def test_parse_payload_supports_json_and_legacy() -> None:
    from api.routes.jobs import _parse_payload

    assert _parse_payload('{"asins":["B1"]}') == {"asins": ["B1"]}
    assert _parse_payload("{'asin': 'B2'}") == {"asin": "B2"}
    assert _parse_payload("not json") == {}


def test_tail_lines_returns_last_n(tmp_path: Path) -> None:
    from api.routes.jobs import _tail_lines

    p = tmp_path / "log.txt"
    p.write_text("\n".join([f"l{i}" for i in range(10)]) + "\n", encoding="utf-8")
    assert _tail_lines(str(p), max_lines=3) == ["l7", "l8", "l9"]


@pytest.mark.asyncio
async def test_job_websocket_closes_when_job_missing() -> None:
    from api.routes import jobs as jobs_routes

    websocket = MagicMock()
    websocket.close = AsyncMock()

    session = AsyncMock()
    session.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)

    await jobs_routes.job_websocket(websocket, uuid4(), session)
    websocket.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_job_websocket_ping_pong_and_disconnect(tmp_path: Path) -> None:
    from api.routes import jobs as jobs_routes

    job_id = uuid4()
    job = Job(
        id=job_id,
        task_type=JobType.DOWNLOAD,
        status=JobStatus.RUNNING,
        progress_percent=5,
        status_message="hi",
        error_message=None,
    )
    session = AsyncMock()
    session.execute.return_value = MagicMock(scalar_one_or_none=lambda: job)

    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    websocket.receive_text = AsyncMock(side_effect=["ping", WebSocketDisconnect()])

    settings = MagicMock()
    settings.downloads_dir = tmp_path
    (tmp_path / ".job_logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".job_logs" / f"{job_id}.log").write_text("hello\n", encoding="utf-8")

    with patch.object(jobs_routes, "get_settings", return_value=settings), patch.object(
        jobs_routes.ws_manager, "connect", AsyncMock()
    ), patch.object(jobs_routes.ws_manager, "disconnect", MagicMock()), patch.object(
        jobs_routes.ws_manager, "send_personal_message", AsyncMock()
    ), patch.object(jobs_routes.job_manager, "set_progress_callback", MagicMock()):
        await jobs_routes.job_websocket(websocket, job_id, session)

    websocket.send_text.assert_awaited_with("pong")


@pytest.mark.asyncio
async def test_jobs_websocket_sends_initial_batch_and_ping_pong() -> None:
    from api.routes import jobs as jobs_routes

    session = AsyncMock()
    session.execute.return_value = MagicMock(
        scalars=lambda: MagicMock(
            all=lambda: [
                Job(id=uuid4(), task_type=JobType.DOWNLOAD, status=JobStatus.RUNNING, progress_percent=1)
            ]
        )
    )

    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    websocket.receive_text = AsyncMock(side_effect=["ping", WebSocketDisconnect()])

    with patch.object(jobs_routes.ws_manager, "connect", AsyncMock()), patch.object(
        jobs_routes.ws_manager, "disconnect", MagicMock()
    ), patch.object(jobs_routes.ws_manager, "send_personal_message", AsyncMock()) as spm:
        await jobs_routes.jobs_websocket(websocket, session)

    assert spm.await_count >= 1
    websocket.send_text.assert_awaited_with("pong")
