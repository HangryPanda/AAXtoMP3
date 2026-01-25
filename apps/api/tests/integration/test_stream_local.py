"""Integration tests for local streaming endpoint."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from db.models import LocalItem


@pytest.mark.asyncio
async def test_stream_local_invalid_id(client: AsyncClient) -> None:
    res = await client.get("/stream/local/not-a-uuid")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_stream_local_forbidden_path(
    client: AsyncClient,
    test_session: AsyncSession,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside.m4b"
    outside.write_bytes(b"x")
    item = LocalItem(title="X", output_path=str(outside))
    test_session.add(item)
    await test_session.commit()
    await test_session.refresh(item)

    settings = Settings(
        converted_dir=tmp_path / "converted",
        completed_dir=tmp_path / "completed",
        downloads_dir=tmp_path / "downloads",
        manifest_dir=tmp_path / "specs",
        core_scripts_dir=tmp_path / "core",
    )
    for d in [settings.converted_dir, settings.completed_dir]:
        d.mkdir(parents=True, exist_ok=True)

    with patch("api.routes.stream.get_settings", return_value=settings):
        res = await client.get(f"/stream/local/{item.id}")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_stream_local_success(
    client: AsyncClient,
    test_session: AsyncSession,
    tmp_path: Path,
) -> None:
    converted = tmp_path / "converted"
    converted.mkdir(parents=True, exist_ok=True)
    f = converted / "ok.m4b"
    f.write_bytes(b"x")

    item = LocalItem(title="OK", output_path=str(f))
    test_session.add(item)
    await test_session.commit()
    await test_session.refresh(item)

    settings = Settings(
        converted_dir=converted,
        completed_dir=tmp_path / "completed",
        downloads_dir=tmp_path / "downloads",
        manifest_dir=tmp_path / "specs",
        core_scripts_dir=tmp_path / "core",
    )
    settings.completed_dir.mkdir(parents=True, exist_ok=True)

    with patch("api.routes.stream.get_settings", return_value=settings):
        res = await client.get(f"/stream/local/{item.id}")
    assert res.status_code == 200

