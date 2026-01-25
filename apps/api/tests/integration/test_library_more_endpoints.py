"""Integration tests for additional library endpoints to improve coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Book,
    BookAsset,
    BookAuthor,
    BookNarrator,
    BookTechnical,
    Chapter,
    Person,
    PlaybackProgress,
)


@pytest.mark.asyncio
async def test_debug_raw_and_book_raw(
    client: AsyncClient,
    test_session: AsyncSession,
) -> None:
    test_session.add(Book(asin="B00RAW", title="Raw Book"))
    await test_session.commit()

    res = await client.get("/library/debug/raw")
    assert res.status_code == 200
    assert any(b["asin"] == "B00RAW" for b in res.json())

    res = await client.get("/library/B00RAW/raw")
    assert res.status_code == 200
    assert res.json()["asin"] == "B00RAW"


@pytest.mark.asyncio
async def test_delete_book_with_delete_files(
    client: AsyncClient,
    test_session: AsyncSession,
    tmp_path: Path,
) -> None:
    aax = tmp_path / "x.aaxc"
    cover = tmp_path / "c.jpg"
    aax.write_bytes(b"x")
    cover.write_bytes(b"c")

    book = Book(asin="B00DEL", title="Del", local_path_aax=str(aax), local_path_cover=str(cover))
    test_session.add(book)
    await test_session.commit()

    res = await client.delete("/library/B00DEL?delete_files=true")
    assert res.status_code == 200
    assert not aax.exists()
    assert not cover.exists()


@pytest.mark.asyncio
async def test_bulk_delete_books(
    client: AsyncClient,
    test_session: AsyncSession,
) -> None:
    test_session.add_all([Book(asin="BDEL1", title="1"), Book(asin="BDEL2", title="2")])
    await test_session.commit()

    res = await client.post("/library/delete", json=["BDEL1", "BDEL2"])
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_repair_dry_run_uses_metadata_extractor(
    client: AsyncClient,
    test_session: AsyncSession,
    tmp_path: Path,
) -> None:
    m4b = tmp_path / "x.m4b"
    m4b.write_bytes(b"x")
    test_session.add(Book(asin="B00DRY", title="Dry", local_path_converted=str(m4b)))
    await test_session.commit()

    with patch("api.routes.library.metadata_extractor") as mock_extractor:
        mock_extractor.extract = AsyncMock(return_value=MagicMock(dict=lambda: {"ok": True}))
        res = await client.get("/library/repair/dry-run/B00DRY")
    assert res.status_code == 200
    assert res.json()["ok"] is True


@pytest.mark.asyncio
async def test_scan_book_success_and_failure(
    client: AsyncClient,
    test_session: AsyncSession,
) -> None:
    # Missing book -> 400
    res = await client.post("/library/B00MISSING/scan")
    assert res.status_code == 400

    # Existing book -> can be forced to succeed via patched manager
    test_session.add(Book(asin="B00SCAN", title="Scan", local_path_converted="/tmp/does-not-matter.m4b"))
    await test_session.commit()

    with patch("api.routes.library.library_manager") as mock_manager:
        mock_manager.scan_book = AsyncMock(return_value=True)
        res = await client.post("/library/B00SCAN/scan")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_scan_library_endpoint_returns_job(
    client: AsyncClient,
) -> None:
    res = await client.post("/library/scan")
    assert res.status_code == 200
    assert "job_id" in res.json()


@pytest.mark.asyncio
async def test_get_book_details_enriched(
    client: AsyncClient,
    test_session: AsyncSession,
    tmp_path: Path,
) -> None:
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"x")

    book = Book(
        asin="B00DETAILS",
        title="Details",
        subtitle="Sub",
        metadata_json={"description": "Desc", "genres": ["G"], "content_type": "Audiobook"},
    )
    author = Person(name="Author")
    narrator = Person(name="Narrator")
    test_session.add_all([book, author, narrator])
    await test_session.commit()
    await test_session.refresh(author)
    await test_session.refresh(narrator)

    test_session.add_all(
        [
            BookAuthor(book_asin="B00DETAILS", person_id=author.id, ordinal=0),
            BookNarrator(book_asin="B00DETAILS", person_id=narrator.id, ordinal=0),
            Chapter(book_asin="B00DETAILS", index=0, title="Ch1", start_offset_ms=0, length_ms=1000, end_offset_ms=1000),
            BookTechnical(book_asin="B00DETAILS", format="m4b", duration_ms=1000),
            BookAsset(book_asin="B00DETAILS", asset_type="cover", path=str(cover)),
            PlaybackProgress(book_asin="B00DETAILS", position_ms=10, playback_speed=1.0, is_finished=False),
        ]
    )
    await test_session.commit()

    res = await client.get("/library/B00DETAILS/details")
    assert res.status_code == 200
    data = res.json()
    assert data["asin"] == "B00DETAILS"
    assert data["title"] == "Details"
    assert data["cover_url"]
