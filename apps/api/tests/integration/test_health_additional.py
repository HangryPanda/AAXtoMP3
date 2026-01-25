"""Additional integration tests for health endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_live(client: AsyncClient) -> None:
    res = await client.get("/health/live")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready(client: AsyncClient) -> None:
    res = await client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in {"ready", "not_ready"}
    assert "database" in data["details"]
    assert "filesystem" in data["details"]


@pytest.mark.asyncio
async def test_health_can_be_healthy(client: AsyncClient, test_settings, tmp_path) -> None:
    downloads = tmp_path / "downloads"
    core = tmp_path / "core"
    downloads.mkdir(parents=True, exist_ok=True)
    core.mkdir(parents=True, exist_ok=True)
    (core / "AAXtoMP3").write_text("#!/bin/bash\necho ok\n", encoding="utf-8")

    # Mutate the injected Settings instance used by the FastAPI dependency override.
    test_settings.downloads_dir = downloads
    test_settings.core_scripts_dir = core

    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"
