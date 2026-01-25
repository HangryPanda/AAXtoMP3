"""Unit tests for JobManager conversion telemetry + throttling."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from services.job_manager import JobManager


@pytest.mark.asyncio
async def test_conversion_meta_emission_is_throttled(tmp_path: Path) -> None:
    """
    Ensure conversion telemetry meta updates are throttled to <= 2/sec,
    while sparse messages still emit on 5% boundaries.
    """
    with patch("services.job_manager.get_settings") as mock_settings, patch(
        "services.job_manager.AudibleClient"
    ), patch("services.job_manager.ConverterEngine"), patch(
        "services.job_manager.MetadataExtractor"
    ), patch("services.job_manager.LibraryManager"):
        mock_settings.return_value = MagicMock(
            max_download_concurrent=5,
            max_convert_concurrent=2,
            downloads_dir=tmp_path / "downloads",
            converted_dir=tmp_path / "converted",
            completed_dir=tmp_path / "completed",
        )
        (tmp_path / "downloads").mkdir(parents=True, exist_ok=True)

        manager = JobManager()
        manager._notify_status = AsyncMock()  # type: ignore[method-assign]
        manager._append_job_log = MagicMock(return_value="LOG")  # type: ignore[method-assign]

        job_id = uuid4()
        wrapper = manager._make_conversion_progress_wrapper(job_id, callback=None)

        # First meta update should emit (monotonic is large in real life); subsequent calls within 0.5s should not.
        with patch(
            "services.job_manager.monotonic",
            side_effect=[100.0, 100.1, 100.2, 100.7],
        ):
            wrapper(1, "line", {"convert_current_ms": 1000, "convert_total_ms": 10_000, "convert_percent": 10})
            wrapper(2, "line", {"convert_current_ms": 2000, "convert_total_ms": 10_000, "convert_percent": 20})
            wrapper(5, "line", {"convert_current_ms": 5000, "convert_total_ms": 10_000, "convert_percent": 50})
            wrapper(6, "line", {"convert_current_ms": 6000, "convert_total_ms": 10_000, "convert_percent": 60})

        # Allow scheduled tasks to run.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        calls = manager._notify_status.call_args_list  # type: ignore[union-attr]
        # Expect:
        # - meta emitted at percent 1 (t=100.0)
        # - message emitted at percent 5 (5% boundary)
        # - meta emitted at percent 6 (t=100.7)
        assert len(calls) == 3

        metas: list[dict[str, object] | None] = []
        messages: list[str | None] = []
        for args, kwargs in calls:
            metas.append(kwargs.get("meta"))
            if "message" in kwargs:
                messages.append(kwargs.get("message"))
            elif len(args) >= 4:
                messages.append(args[3])
            else:
                messages.append(None)

        # One message call at 5%.
        assert any(m == "Converting: 5%" for m in messages)

        # Two meta calls; meta excludes convert_percent.
        meta_calls = [m for m in metas if m is not None]
        assert len(meta_calls) == 2
        assert all("convert_current_ms" in m and "convert_total_ms" in m for m in meta_calls)
        assert all("convert_percent" not in m for m in meta_calls)


def test_conversion_log_lines_do_not_emit_status(tmp_path: Path) -> None:
    with patch("services.job_manager.get_settings") as mock_settings, patch(
        "services.job_manager.AudibleClient"
    ), patch("services.job_manager.ConverterEngine"), patch(
        "services.job_manager.MetadataExtractor"
    ), patch("services.job_manager.LibraryManager"):
        mock_settings.return_value = MagicMock(
            max_download_concurrent=5,
            max_convert_concurrent=2,
            downloads_dir=tmp_path / "downloads",
            converted_dir=tmp_path / "converted",
            completed_dir=tmp_path / "completed",
        )
        (tmp_path / "downloads").mkdir(parents=True, exist_ok=True)

        manager = JobManager()
        manager._notify_status = AsyncMock()  # type: ignore[method-assign]
        manager._append_job_log = MagicMock(return_value="LOG")  # type: ignore[method-assign]

        job_id = uuid4()
        wrapper = manager._make_conversion_progress_wrapper(job_id, callback=None)
        wrapper(-1, "some log line", None)

        manager._append_job_log.assert_called_once()
        manager._notify_status.assert_not_called()  # type: ignore[union-attr]
