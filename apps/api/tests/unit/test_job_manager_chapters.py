"""Unit tests for JobManager chapter extraction helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.config import Settings
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
        return JobManager()


@pytest.mark.asyncio
async def test_extract_chapters_from_aax_success(manager: JobManager, tmp_path: Path) -> None:
    input_file = tmp_path / "in.aaxc"
    input_file.write_bytes(b"x")
    out = tmp_path / "chapters.json"

    ffprobe_out = {
        "chapters": [
            {"id": 0, "start_time": "0.0", "end_time": "1.0", "tags": {"title": "Intro"}},
            {"id": 1, "start_time": "1.0", "end_time": "2.5", "tags": {}},
        ]
    }

    proc = SimpleNamespace(
        returncode=0,
        communicate=AsyncMock(return_value=(json.dumps(ffprobe_out).encode("utf-8"), b"")),
    )

    with patch("services.job_manager.asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        ok = await manager._extract_chapters_from_aax(input_file, out, asin="B012345678")

    assert ok is True
    data = json.loads(out.read_text(encoding="utf-8"))
    chapters = data["content_metadata"]["chapter_info"]["chapters"]
    assert chapters[0]["title"] == "Intro"
    assert chapters[1]["title"].startswith("Chapter")


@pytest.mark.asyncio
async def test_extract_chapters_from_aax_handles_ffprobe_failure(manager: JobManager, tmp_path: Path) -> None:
    input_file = tmp_path / "in.aaxc"
    input_file.write_bytes(b"x")
    out = tmp_path / "chapters.json"

    proc = SimpleNamespace(
        returncode=1,
        communicate=AsyncMock(return_value=(b"", b"bad")),
    )

    with patch("services.job_manager.asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        ok = await manager._extract_chapters_from_aax(input_file, out, asin=None)

    assert ok is False

