"""Additional integration tests for library endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Book, BookAsset, Job, JobStatus, JobType, LocalItem, PlaybackProgress, Series


@pytest.mark.asyncio
async def test_list_series_and_filter(
    client: AsyncClient,
    test_session: AsyncSession,
) -> None:
    test_session.add_all([Series(name="Alpha"), Series(name="Beta")])
    await test_session.commit()

    res = await client.get("/library/series")
    assert res.status_code == 200
    assert len(res.json()) == 2

    res = await client.get("/library/series?q=Alp")
    assert res.status_code == 200
    assert len(res.json()) == 1


@pytest.mark.asyncio
async def test_sync_status_idle_and_running(
    client: AsyncClient,
    test_session: AsyncSession,
) -> None:
    res = await client.get("/library/sync/status")
    assert res.status_code == 200
    assert res.json()["status"] == "idle"

    job = Job(task_type=JobType.SYNC, status=JobStatus.RUNNING, progress_percent=50)
    test_session.add(job)
    await test_session.commit()

    res = await client.get("/library/sync/status")
    assert res.status_code == 200
    assert res.json()["status"] == "running"


@pytest.mark.asyncio
async def test_incomplete_downloads_reads_manifest(
    client: AsyncClient,
    test_session: AsyncSession,
    tmp_path: Path,
) -> None:
    manifest_dir = tmp_path / "specs"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "download_manifest.json").write_text(
        json.dumps(
            {
                "B00PARTIAL": {
                    "status": "partial",
                    "title": "Partial Book",
                    "cover_path": "/covers/x.jpg",
                    "downloaded_at": "now",
                }
            }
        ),
        encoding="utf-8",
    )

    test_session.add(Book(asin="B00PARTIAL", title="Partial Book"))
    await test_session.commit()

    with patch("core.config.get_settings") as mock_get_settings:
        settings = mock_get_settings.return_value
        settings.manifest_dir = manifest_dir
        res = await client.get("/library/downloads/incomplete")

    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["asin"] == "B00PARTIAL"


@pytest.mark.asyncio
async def test_local_items_list_and_get(
    client: AsyncClient,
    test_session: AsyncSession,
) -> None:
    item = LocalItem(title="Local", output_path="/data/converted/local.m4b")
    test_session.add(item)
    await test_session.commit()
    await test_session.refresh(item)

    res = await client.get("/library/local")
    assert res.status_code == 200
    assert len(res.json()) == 1

    res = await client.get(f"/library/local/{item.id}")
    assert res.status_code == 200
    assert res.json()["id"] == str(item.id)


@pytest.mark.asyncio
async def test_cover_and_progress_endpoints(
    client: AsyncClient,
    test_session: AsyncSession,
    tmp_path: Path,
) -> None:
    cover = tmp_path / "c.jpg"
    cover.write_bytes(b"img")

    book = Book(asin="B00COVER", title="Cover Book")
    asset = BookAsset(book_asin="B00COVER", asset_type="cover", path=str(cover))
    test_session.add_all([book, asset])
    await test_session.commit()

    res = await client.get("/library/B00COVER/cover")
    assert res.status_code == 200

    res = await client.get("/library/B00COVER/progress")
    assert res.status_code == 200
    assert res.json() is None

    res = await client.patch(
        "/library/B00COVER/progress",
        json={"position_ms": 1000, "chapter_id": None, "playback_speed": 1.0, "is_finished": False},
    )
    assert res.status_code == 200
    assert res.json()["position_ms"] == 1000

    res = await client.get("/library/B00COVER/progress")
    assert res.status_code == 200
    assert res.json()["position_ms"] == 1000


@pytest.mark.asyncio
async def test_continue_listening_orders_by_last_played(
    client: AsyncClient,
    test_session: AsyncSession,
) -> None:
    b1 = Book(asin="B1", title="B1")
    b2 = Book(asin="B2", title="B2")
    test_session.add_all([b1, b2])
    await test_session.commit()

    p1 = PlaybackProgress(book_asin="B1", position_ms=1, playback_speed=1.0, is_finished=False)
    p2 = PlaybackProgress(book_asin="B2", position_ms=2, playback_speed=1.0, is_finished=False)
    test_session.add_all([p1, p2])
    await test_session.commit()

    res = await client.get("/library/continue-listening?limit=2")
    assert res.status_code == 200
    assert len(res.json()) == 2

