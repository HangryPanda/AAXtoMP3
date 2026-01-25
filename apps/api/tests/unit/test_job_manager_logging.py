"""Unit tests for JobManager job log persistence."""

from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from services.job_manager import JobManager


def test_append_job_log_persists_under_downloads_dir(tmp_path: Path) -> None:
    """Job logs are persisted under downloads_dir/.job_logs so they survive container restarts."""
    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    with patch("services.job_manager.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            max_download_concurrent=5,
            max_convert_concurrent=2,
            downloads_dir=downloads_dir,
            converted_dir=tmp_path / "converted",
            completed_dir=tmp_path / "completed",
        )

        manager = JobManager()
        job_id = uuid4()
        line = manager._append_job_log(job_id, "INFO", "hello")

        assert "hello" in line
        log_path = downloads_dir / ".job_logs" / f"{job_id}.log"
        assert log_path.exists()
        assert "hello" in log_path.read_text(encoding="utf-8")

