"""Tests for JobManager conversion manifest updates and source file moving."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestConversionUpdatesManifest:
    """Tests for converted_manifest.json updates after conversion."""

    @pytest.mark.asyncio
    async def test_conversion_updates_manifest_on_success(self, tmp_path: Path) -> None:
        """Verify manifest is updated after successful conversion."""
        from services.job_manager import JobManager

        downloads_dir = tmp_path / "downloads"
        converted_dir = tmp_path / "converted"
        completed_dir = tmp_path / "completed"
        manifest_dir = tmp_path / "specs"

        downloads_dir.mkdir()
        converted_dir.mkdir()
        completed_dir.mkdir()
        manifest_dir.mkdir()

        # Create input files
        aaxc_file = downloads_dir / "B00TEST123_Title.aaxc"
        voucher_file = downloads_dir / "B00TEST123_Title.voucher"
        aaxc_file.write_bytes(b"content")
        voucher_file.write_text("{}")

        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=downloads_dir,
                converted_dir=converted_dir,
                completed_dir=completed_dir,
                manifest_dir=manifest_dir,
                move_after_complete=False,
                data_dir=tmp_path,
            )

            manager = JobManager()

            # Mock converter to return success
            output_file = converted_dir / "Test Book.m4b"
            output_file.write_bytes(b"converted")
            manager.converter = MagicMock()
            manager.converter.convert = AsyncMock(
                return_value={
                    "success": True,
                    "returncode": 0,
                    "output_files": [str(output_file)],
                }
            )

            job_id = uuid4()
            result = await manager._execute_conversion(
                job_id, "B00TEST123", "m4b", None
            )

            assert result["success"] is True

            # Check manifest was updated
            manifest_path = manifest_dir / "converted_manifest.json"
            assert manifest_path.exists(), "Manifest file should be created"

            manifest = json.loads(manifest_path.read_text())
            assert len(manifest) > 0, "Manifest should have at least one entry"

            # Find entry by source path
            key = str(aaxc_file)
            assert key in manifest, f"Manifest should have key {key}"
            entry = manifest[key]
            assert entry["status"] == "success"
            assert entry["asin"] == "B00TEST123"

    @pytest.mark.asyncio
    async def test_conversion_manifest_entry_schema(self, tmp_path: Path) -> None:
        """Verify entry contains: status, asin, title, output_path, started_at, ended_at."""
        from services.job_manager import JobManager

        downloads_dir = tmp_path / "downloads"
        converted_dir = tmp_path / "converted"
        completed_dir = tmp_path / "completed"
        manifest_dir = tmp_path / "specs"

        for d in [downloads_dir, converted_dir, completed_dir, manifest_dir]:
            d.mkdir()

        aaxc_file = downloads_dir / "B00TEST123_Title.aaxc"
        voucher_file = downloads_dir / "B00TEST123_Title.voucher"
        aaxc_file.write_bytes(b"content")
        voucher_file.write_text("{}")

        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=downloads_dir,
                converted_dir=converted_dir,
                completed_dir=completed_dir,
                manifest_dir=manifest_dir,
                move_after_complete=False,
                data_dir=tmp_path,
            )

            manager = JobManager()

            output_file = converted_dir / "Test Book.m4b"
            output_file.write_bytes(b"converted")
            manager.converter = MagicMock()
            manager.converter.convert = AsyncMock(
                return_value={
                    "success": True,
                    "returncode": 0,
                    "output_files": [str(output_file)],
                }
            )

            job_id = uuid4()
            await manager._execute_conversion(job_id, "B00TEST123", "m4b", None)

            manifest_path = manifest_dir / "converted_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            key = str(aaxc_file)
            entry = manifest[key]

            # Check all required fields
            assert "status" in entry
            assert "asin" in entry
            assert "title" in entry
            assert "output_path" in entry
            assert "started_at" in entry
            assert "ended_at" in entry

            # Validate timestamps are ISO format
            datetime.fromisoformat(entry["started_at"])
            datetime.fromisoformat(entry["ended_at"])

    @pytest.mark.asyncio
    async def test_conversion_manifest_key_is_source_path(self, tmp_path: Path) -> None:
        """Verify the key is the source AAXC path (matching worker.py)."""
        from services.job_manager import JobManager

        downloads_dir = tmp_path / "downloads"
        converted_dir = tmp_path / "converted"
        completed_dir = tmp_path / "completed"
        manifest_dir = tmp_path / "specs"

        for d in [downloads_dir, converted_dir, completed_dir, manifest_dir]:
            d.mkdir()

        # Use a specific path to verify
        aaxc_file = downloads_dir / "B00MYASIN1_My_Test_Book.aaxc"
        voucher_file = downloads_dir / "B00MYASIN1_My_Test_Book.voucher"
        aaxc_file.write_bytes(b"content")
        voucher_file.write_text("{}")

        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=downloads_dir,
                converted_dir=converted_dir,
                completed_dir=completed_dir,
                manifest_dir=manifest_dir,
                move_after_complete=False,
                data_dir=tmp_path,
            )

            manager = JobManager()

            output_file = converted_dir / "Test Book.m4b"
            output_file.write_bytes(b"converted")
            manager.converter = MagicMock()
            manager.converter.convert = AsyncMock(
                return_value={
                    "success": True,
                    "returncode": 0,
                    "output_files": [str(output_file)],
                }
            )

            job_id = uuid4()
            await manager._execute_conversion(job_id, "B00MYASIN1", "m4b", None)

            manifest_path = manifest_dir / "converted_manifest.json"
            manifest = json.loads(manifest_path.read_text())

            # The key should be the full source path
            expected_key = str(aaxc_file)
            assert expected_key in manifest, f"Key should be source path: {expected_key}"

    @pytest.mark.asyncio
    async def test_conversion_does_not_update_manifest_on_failure(
        self, tmp_path: Path
    ) -> None:
        """Verify failed conversions update manifest with failed status but don't corrupt it."""
        from services.job_manager import JobManager

        downloads_dir = tmp_path / "downloads"
        converted_dir = tmp_path / "converted"
        completed_dir = tmp_path / "completed"
        manifest_dir = tmp_path / "specs"

        for d in [downloads_dir, converted_dir, completed_dir, manifest_dir]:
            d.mkdir()

        aaxc_file = downloads_dir / "B00FAILED1_Title.aaxc"
        voucher_file = downloads_dir / "B00FAILED1_Title.voucher"
        aaxc_file.write_bytes(b"content")
        voucher_file.write_text("{}")

        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=downloads_dir,
                converted_dir=converted_dir,
                completed_dir=completed_dir,
                manifest_dir=manifest_dir,
                move_after_complete=False,
                data_dir=tmp_path,
            )

            manager = JobManager()

            manager.converter = MagicMock()
            manager.converter.convert = AsyncMock(
                return_value={
                    "success": False,
                    "returncode": 1,
                    "error": "Conversion failed",
                    "stderr": "Some error occurred",
                }
            )

            job_id = uuid4()
            result = await manager._execute_conversion(
                job_id, "B00FAILED1", "m4b", None
            )

            assert result["success"] is False

            # Check manifest was updated with failed status
            manifest_path = manifest_dir / "converted_manifest.json"
            assert manifest_path.exists(), "Manifest should be created even for failures"

            manifest = json.loads(manifest_path.read_text())
            key = str(aaxc_file)
            assert key in manifest, "Failed conversion should still add manifest entry"
            entry = manifest[key]
            assert entry["status"] == "failed"
            assert "error" in entry


class TestMoveSourcesAfterConversion:
    """Tests for moving source files to completed_dir after conversion."""

    @pytest.mark.asyncio
    async def test_move_sources_moves_all_files(self, tmp_path: Path) -> None:
        """Verify AAXC, voucher, chapters.json, and cover are moved."""
        from services.job_manager import JobManager

        downloads_dir = tmp_path / "downloads"
        converted_dir = tmp_path / "converted"
        completed_dir = tmp_path / "completed"
        manifest_dir = tmp_path / "specs"

        for d in [downloads_dir, converted_dir, completed_dir, manifest_dir]:
            d.mkdir()

        # Create all source files
        aaxc_file = downloads_dir / "B00MOVE123_Title.aaxc"
        voucher_file = downloads_dir / "B00MOVE123_Title.voucher"
        chapters_file = downloads_dir / "B00MOVE123_Title-chapters.json"
        cover_file = downloads_dir / "B00MOVE123_Title.jpg"

        aaxc_file.write_bytes(b"aaxc content")
        voucher_file.write_text("{}")
        chapters_file.write_text("[]")
        cover_file.write_bytes(b"jpg content")

        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=downloads_dir,
                converted_dir=converted_dir,
                completed_dir=completed_dir,
                manifest_dir=manifest_dir,
                move_after_complete=True,
                data_dir=tmp_path,
            )

            manager = JobManager()

            output_file = converted_dir / "Test Book.m4b"
            output_file.write_bytes(b"converted")
            manager.converter = MagicMock()
            manager.converter.convert = AsyncMock(
                return_value={
                    "success": True,
                    "returncode": 0,
                    "output_files": [str(output_file)],
                }
            )

            job_id = uuid4()
            await manager._execute_conversion(job_id, "B00MOVE123", "m4b", None)

            # Verify files were moved
            assert not aaxc_file.exists(), "AAXC should be moved"
            assert not voucher_file.exists(), "Voucher should be moved"
            assert not chapters_file.exists(), "Chapters JSON should be moved"
            assert not cover_file.exists(), "Cover should be moved"

            # Verify files exist in completed_dir
            assert (completed_dir / "B00MOVE123_Title.aaxc").exists()
            assert (completed_dir / "B00MOVE123_Title.voucher").exists()
            assert (completed_dir / "B00MOVE123_Title-chapters.json").exists()
            assert (completed_dir / "B00MOVE123_Title.jpg").exists()

    @pytest.mark.asyncio
    async def test_move_sources_respects_setting(self, tmp_path: Path) -> None:
        """Verify files only move when move_after_complete=True."""
        from services.job_manager import JobManager

        downloads_dir = tmp_path / "downloads"
        converted_dir = tmp_path / "converted"
        completed_dir = tmp_path / "completed"
        manifest_dir = tmp_path / "specs"

        for d in [downloads_dir, converted_dir, completed_dir, manifest_dir]:
            d.mkdir()

        aaxc_file = downloads_dir / "B00STAY123_Title.aaxc"
        voucher_file = downloads_dir / "B00STAY123_Title.voucher"
        aaxc_file.write_bytes(b"content")
        voucher_file.write_text("{}")

        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=downloads_dir,
                converted_dir=converted_dir,
                completed_dir=completed_dir,
                manifest_dir=manifest_dir,
                move_after_complete=False,  # Disabled
                data_dir=tmp_path,
            )

            manager = JobManager()

            output_file = converted_dir / "Test Book.m4b"
            output_file.write_bytes(b"converted")
            manager.converter = MagicMock()
            manager.converter.convert = AsyncMock(
                return_value={
                    "success": True,
                    "returncode": 0,
                    "output_files": [str(output_file)],
                }
            )

            job_id = uuid4()
            await manager._execute_conversion(job_id, "B00STAY123", "m4b", None)

            # Verify files were NOT moved
            assert aaxc_file.exists(), "AAXC should stay when setting is False"
            assert voucher_file.exists(), "Voucher should stay when setting is False"

    @pytest.mark.asyncio
    async def test_move_sources_handles_missing_files(self, tmp_path: Path) -> None:
        """Verify graceful handling when some files don't exist."""
        from services.job_manager import JobManager

        downloads_dir = tmp_path / "downloads"
        converted_dir = tmp_path / "converted"
        completed_dir = tmp_path / "completed"
        manifest_dir = tmp_path / "specs"

        for d in [downloads_dir, converted_dir, completed_dir, manifest_dir]:
            d.mkdir()

        # Only create AAXC and voucher, no chapters or cover
        aaxc_file = downloads_dir / "B00PART123_Title.aaxc"
        voucher_file = downloads_dir / "B00PART123_Title.voucher"
        aaxc_file.write_bytes(b"content")
        voucher_file.write_text("{}")

        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=downloads_dir,
                converted_dir=converted_dir,
                completed_dir=completed_dir,
                manifest_dir=manifest_dir,
                move_after_complete=True,
                data_dir=tmp_path,
            )

            manager = JobManager()

            output_file = converted_dir / "Test Book.m4b"
            output_file.write_bytes(b"converted")
            manager.converter = MagicMock()
            manager.converter.convert = AsyncMock(
                return_value={
                    "success": True,
                    "returncode": 0,
                    "output_files": [str(output_file)],
                }
            )

            job_id = uuid4()
            # Should not raise an exception
            result = await manager._execute_conversion(
                job_id, "B00PART123", "m4b", None
            )

            assert result["success"] is True

            # Verify the files that existed were moved
            assert not aaxc_file.exists(), "AAXC should be moved"
            assert not voucher_file.exists(), "Voucher should be moved"
            assert (completed_dir / "B00PART123_Title.aaxc").exists()
            assert (completed_dir / "B00PART123_Title.voucher").exists()

    @pytest.mark.asyncio
    async def test_move_sources_does_not_move_on_failure(self, tmp_path: Path) -> None:
        """Verify files are not moved when conversion fails."""
        from services.job_manager import JobManager

        downloads_dir = tmp_path / "downloads"
        converted_dir = tmp_path / "converted"
        completed_dir = tmp_path / "completed"
        manifest_dir = tmp_path / "specs"

        for d in [downloads_dir, converted_dir, completed_dir, manifest_dir]:
            d.mkdir()

        aaxc_file = downloads_dir / "B00FAIL999_Title.aaxc"
        voucher_file = downloads_dir / "B00FAIL999_Title.voucher"
        aaxc_file.write_bytes(b"content")
        voucher_file.write_text("{}")

        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=downloads_dir,
                converted_dir=converted_dir,
                completed_dir=completed_dir,
                manifest_dir=manifest_dir,
                move_after_complete=True,
                data_dir=tmp_path,
            )

            manager = JobManager()

            manager.converter = MagicMock()
            manager.converter.convert = AsyncMock(
                return_value={
                    "success": False,
                    "returncode": 1,
                    "error": "Conversion failed",
                }
            )

            job_id = uuid4()
            result = await manager._execute_conversion(
                job_id, "B00FAIL999", "m4b", None
            )

            assert result["success"] is False

            # Files should NOT be moved on failure
            assert aaxc_file.exists(), "AAXC should stay on failure"
            assert voucher_file.exists(), "Voucher should stay on failure"
