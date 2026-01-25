"""Unit tests for JobManager sync/repair execution paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.config import Settings
from db.models import Book
from services.job_manager import JobManager


@pytest.fixture
def manager(tmp_path: Path) -> JobManager:
    settings = Settings(
        downloads_dir=tmp_path / "downloads",
        converted_dir=tmp_path / "converted",
        completed_dir=tmp_path / "completed",
        manifest_dir=tmp_path / "specs",
        core_scripts_dir=tmp_path / "core",
    )
    for d in [settings.downloads_dir, settings.converted_dir, settings.completed_dir, settings.manifest_dir]:
        d.mkdir(parents=True, exist_ok=True)

    with patch("services.job_manager.get_settings", return_value=settings):
        mgr = JobManager()
        mgr.audible_client = MagicMock()
        mgr.converter = MagicMock()
        mgr.metadata_extractor = MagicMock()
        mgr.library_manager = MagicMock()
        return mgr


@pytest.mark.asyncio
async def test_execute_sync_fails_when_not_authenticated(manager: JobManager) -> None:
    job_id = uuid4()
    manager.audible_client.is_authenticated = AsyncMock(return_value=False)

    with patch.object(manager, "_notify_status", AsyncMock()):
        result = await manager._execute_sync(job_id)

    assert result["success"] is False
    assert "Not authenticated" in (result.get("error") or "")


@pytest.mark.asyncio
async def test_execute_sync_upserts_books(manager: JobManager, test_session: AsyncSession) -> None:
    job_id = uuid4()
    manager.audible_client.is_authenticated = AsyncMock(return_value=True)
    manager.audible_client.get_library = AsyncMock(
        return_value=[
            {
                "asin": "SYNC001",
                "title": "Sync Title",
                "subtitle": "Sub",
                "authors": [{"name": "A"}],
                "narrators": [{"name": "N"}],
                "runtime_length_min": "120",
                "product_images": "http://example.test/cover.jpg",
            }
        ]
    )

    with patch("services.job_manager.get_session") as mock_get_session, patch.object(manager, "_notify_status", AsyncMock()):
        async def yield_session():
            yield test_session
        mock_get_session.side_effect = yield_session

        result = await manager._execute_sync(job_id)

    assert result["success"] is True
    res = await test_session.execute(select(Book).where(Book.asin == "SYNC001"))
    book = res.scalar_one_or_none()
    assert book is not None
    assert book.title == "Sync Title"
    assert book.metadata_json and book.metadata_json.get("asin") == "SYNC001"


@pytest.mark.asyncio
async def test_execute_repair_calls_apply_repair_and_emits_summary(manager: JobManager) -> None:
    job_id = uuid4()
    manager._progress_callbacks[job_id] = lambda _p, _line: None

    fake_result = {
        "updated_books": 1,
        "inserted_local_items": 2,
        "deduped_local_items": 0,
        "duplicate_asins": 1,
        "duplicates_report_path": "/tmp/report.tsv",
        "updates_breakdown": {"set_local_path_converted": 1, "set_status_completed": 1},
    }

    with patch("services.job_manager.get_session") as mock_get_session, patch(
        "services.job_manager.apply_repair", AsyncMock(return_value=fake_result)
    ), patch.object(manager, "_notify_status", AsyncMock()):
        session = AsyncMock(spec=AsyncSession)

        async def yield_session():
            yield session
        mock_get_session.side_effect = yield_session

        result = await manager._execute_repair(job_id)

    assert result["success"] is True
    assert result["duplicate_asins"] == 1

