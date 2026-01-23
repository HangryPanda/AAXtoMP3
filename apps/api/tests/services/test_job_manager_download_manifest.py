"""Unit tests for download manifest updates in JobManager."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.job_manager import JobManager


class TestDownloadManifestUpdate:
    """Tests for download manifest updates after successful downloads."""

    def _create_mock_settings(self, tmp_path: Path) -> MagicMock:
        """Create a mock settings object with tmp_path directories."""
        return MagicMock(
            max_download_concurrent=5,
            max_convert_concurrent=2,
            downloads_dir=tmp_path / "downloads",
            converted_dir=tmp_path / "converted",
            completed_dir=tmp_path / "completed",
            manifest_dir=tmp_path / "manifests",
            data_dir=tmp_path / "data",
        )

    @pytest.mark.asyncio
    async def test_download_updates_manifest_on_success(self, tmp_path: Path) -> None:
        """Verify manifest JSON is updated with correct schema after successful download."""
        with patch("services.job_manager.get_settings") as mock_settings:
            settings = self._create_mock_settings(tmp_path)
            mock_settings.return_value = settings

            # Create required directories
            settings.manifest_dir.mkdir(parents=True, exist_ok=True)
            settings.downloads_dir.mkdir(parents=True, exist_ok=True)

            manager = JobManager()
            manager.audible_client = MagicMock()

            # Mock successful download result
            asin = "B00TEST123"
            aaxc_path = str(settings.downloads_dir / f"{asin}_Title.aaxc")
            voucher_path = str(settings.downloads_dir / f"{asin}_Title.voucher")
            cover_path = str(settings.downloads_dir / f"{asin}_Title_(1215).jpg")

            manager.audible_client.download = AsyncMock(return_value={
                "success": True,
                "asin": asin,
                "output_dir": str(settings.downloads_dir),
                "files": [aaxc_path, voucher_path, cover_path],
            })

            # Mock database session to avoid DB calls
            with patch("services.job_manager.get_session") as mock_get_session:
                mock_session = AsyncMock()
                mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
                mock_session.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

                async def session_gen():
                    yield mock_session
                mock_get_session.return_value = session_gen()

                from uuid import uuid4
                job_id = uuid4()

                await manager._execute_download(job_id, [asin])

            # Verify manifest was created/updated
            manifest_path = settings.manifest_dir / "download_manifest.json"
            assert manifest_path.exists(), "Manifest file should exist after successful download"

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert asin in manifest, f"ASIN {asin} should be in manifest"

            entry = manifest[asin]
            assert entry["status"] == "success"
            assert entry["asin"] == asin
            assert "downloaded_at" in entry

    @pytest.mark.asyncio
    async def test_download_manifest_entry_schema(self, tmp_path: Path) -> None:
        """Verify the entry contains: asin, title, aaxc_path, voucher_path, cover_path, downloaded_at, status."""
        with patch("services.job_manager.get_settings") as mock_settings:
            settings = self._create_mock_settings(tmp_path)
            mock_settings.return_value = settings

            # Create required directories
            settings.manifest_dir.mkdir(parents=True, exist_ok=True)
            settings.downloads_dir.mkdir(parents=True, exist_ok=True)

            manager = JobManager()
            manager.audible_client = MagicMock()

            asin = "B00SCHEMA1"
            title = "Test Book Title"
            aaxc_path = str(settings.downloads_dir / f"{asin}_{title}.aaxc")
            voucher_path = str(settings.downloads_dir / f"{asin}_{title}.voucher")
            cover_path = str(settings.downloads_dir / f"{asin}_{title}_(1215).jpg")

            manager.audible_client.download = AsyncMock(return_value={
                "success": True,
                "asin": asin,
                "title": title,
                "output_dir": str(settings.downloads_dir),
                "files": [aaxc_path, voucher_path, cover_path],
            })

            # Mock database session with a book that has a title
            with patch("services.job_manager.get_session") as mock_get_session:
                mock_book = MagicMock()
                mock_book.asin = asin
                mock_book.title = title

                mock_session = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_book])))
                mock_result.scalar_one_or_none = MagicMock(return_value=mock_book)
                mock_session.execute = AsyncMock(return_value=mock_result)
                mock_session.add = MagicMock()
                mock_session.commit = AsyncMock()

                async def session_gen():
                    yield mock_session
                mock_get_session.return_value = session_gen()

                from uuid import uuid4
                job_id = uuid4()

                await manager._execute_download(job_id, [asin])

            # Verify manifest schema
            manifest_path = settings.manifest_dir / "download_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            assert asin in manifest
            entry = manifest[asin]

            # Check all required fields
            required_fields = ["asin", "title", "aaxc_path", "voucher_path", "cover_path", "downloaded_at", "status"]
            for field in required_fields:
                assert field in entry, f"Field '{field}' should be in manifest entry"

            # Verify field values
            assert entry["asin"] == asin
            assert entry["title"] == title
            assert entry["aaxc_path"] == aaxc_path
            assert entry["voucher_path"] == voucher_path
            assert entry["cover_path"] == cover_path
            assert entry["status"] == "success"

            # Verify downloaded_at is valid ISO format
            try:
                datetime.fromisoformat(entry["downloaded_at"])
            except ValueError:
                pytest.fail("downloaded_at should be a valid ISO format timestamp")

    @pytest.mark.asyncio
    async def test_download_does_not_update_manifest_on_failure(self, tmp_path: Path) -> None:
        """Verify failed downloads do not corrupt manifest."""
        with patch("services.job_manager.get_settings") as mock_settings:
            settings = self._create_mock_settings(tmp_path)
            mock_settings.return_value = settings

            # Create required directories
            settings.manifest_dir.mkdir(parents=True, exist_ok=True)
            settings.downloads_dir.mkdir(parents=True, exist_ok=True)

            # Pre-populate manifest with an existing entry
            manifest_path = settings.manifest_dir / "download_manifest.json"
            existing_manifest = {
                "B00EXISTING": {
                    "asin": "B00EXISTING",
                    "title": "Existing Book",
                    "aaxc_path": "/path/to/existing.aaxc",
                    "voucher_path": "/path/to/existing.voucher",
                    "cover_path": "/path/to/existing.jpg",
                    "downloaded_at": "2026-01-01T00:00:00",
                    "status": "success"
                }
            }
            manifest_path.write_text(json.dumps(existing_manifest, indent=2), encoding="utf-8")

            manager = JobManager()
            manager.audible_client = MagicMock()

            # Mock failed download
            failing_asin = "B00FAILING"
            manager.audible_client.download = AsyncMock(return_value={
                "success": False,
                "asin": failing_asin,
                "error": "Download failed",
            })

            # Mock database session
            with patch("services.job_manager.get_session") as mock_get_session:
                mock_session = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
                mock_session.execute = AsyncMock(return_value=mock_result)

                async def session_gen():
                    yield mock_session
                mock_get_session.return_value = session_gen()

                from uuid import uuid4
                job_id = uuid4()

                await manager._execute_download(job_id, [failing_asin])

            # Verify manifest was not corrupted
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            # Existing entry should still be present and unchanged
            assert "B00EXISTING" in manifest
            assert manifest["B00EXISTING"]["title"] == "Existing Book"
            assert manifest["B00EXISTING"]["status"] == "success"

            # Failed download should NOT be in manifest
            assert failing_asin not in manifest, "Failed downloads should not be added to manifest"

    @pytest.mark.asyncio
    async def test_download_manifest_preserves_existing_entries(self, tmp_path: Path) -> None:
        """Verify updating does not clobber other entries."""
        with patch("services.job_manager.get_settings") as mock_settings:
            settings = self._create_mock_settings(tmp_path)
            mock_settings.return_value = settings

            # Create required directories
            settings.manifest_dir.mkdir(parents=True, exist_ok=True)
            settings.downloads_dir.mkdir(parents=True, exist_ok=True)

            # Pre-populate manifest with existing entries
            manifest_path = settings.manifest_dir / "download_manifest.json"
            existing_manifest = {
                "B00BOOK001": {
                    "asin": "B00BOOK001",
                    "title": "First Book",
                    "aaxc_path": "/path/to/book1.aaxc",
                    "voucher_path": "/path/to/book1.voucher",
                    "cover_path": "/path/to/book1.jpg",
                    "downloaded_at": "2026-01-01T00:00:00",
                    "status": "success"
                },
                "B00BOOK002": {
                    "asin": "B00BOOK002",
                    "title": "Second Book",
                    "aaxc_path": "/path/to/book2.aaxc",
                    "voucher_path": "/path/to/book2.voucher",
                    "cover_path": "/path/to/book2.jpg",
                    "downloaded_at": "2026-01-02T00:00:00",
                    "status": "success"
                }
            }
            manifest_path.write_text(json.dumps(existing_manifest, indent=2), encoding="utf-8")

            manager = JobManager()
            manager.audible_client = MagicMock()

            # Download a new book
            new_asin = "B00BOOK003"
            new_title = "Third Book"
            aaxc_path = str(settings.downloads_dir / f"{new_asin}_{new_title}.aaxc")
            voucher_path = str(settings.downloads_dir / f"{new_asin}_{new_title}.voucher")
            cover_path = str(settings.downloads_dir / f"{new_asin}_{new_title}.jpg")

            manager.audible_client.download = AsyncMock(return_value={
                "success": True,
                "asin": new_asin,
                "title": new_title,
                "output_dir": str(settings.downloads_dir),
                "files": [aaxc_path, voucher_path, cover_path],
            })

            # Mock database session
            with patch("services.job_manager.get_session") as mock_get_session:
                mock_book = MagicMock()
                mock_book.asin = new_asin
                mock_book.title = new_title

                mock_session = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_book])))
                mock_result.scalar_one_or_none = MagicMock(return_value=mock_book)
                mock_session.execute = AsyncMock(return_value=mock_result)
                mock_session.add = MagicMock()
                mock_session.commit = AsyncMock()

                async def session_gen():
                    yield mock_session
                mock_get_session.return_value = session_gen()

                from uuid import uuid4
                job_id = uuid4()

                await manager._execute_download(job_id, [new_asin])

            # Verify manifest preserves all entries
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            # All existing entries should be preserved
            assert "B00BOOK001" in manifest
            assert manifest["B00BOOK001"]["title"] == "First Book"

            assert "B00BOOK002" in manifest
            assert manifest["B00BOOK002"]["title"] == "Second Book"

            # New entry should be added
            assert new_asin in manifest
            assert manifest[new_asin]["title"] == new_title
            assert manifest[new_asin]["status"] == "success"

    @pytest.mark.asyncio
    async def test_download_manifest_handles_missing_file(self, tmp_path: Path) -> None:
        """Verify manifest is created if it does not exist."""
        with patch("services.job_manager.get_settings") as mock_settings:
            settings = self._create_mock_settings(tmp_path)
            mock_settings.return_value = settings

            # Create required directories but NOT the manifest
            settings.manifest_dir.mkdir(parents=True, exist_ok=True)
            settings.downloads_dir.mkdir(parents=True, exist_ok=True)

            manifest_path = settings.manifest_dir / "download_manifest.json"
            assert not manifest_path.exists(), "Manifest should not exist before test"

            manager = JobManager()
            manager.audible_client = MagicMock()

            asin = "B00NEWBOOK"
            title = "New Book"
            aaxc_path = str(settings.downloads_dir / f"{asin}.aaxc")
            voucher_path = str(settings.downloads_dir / f"{asin}.voucher")
            cover_path = str(settings.downloads_dir / f"{asin}.jpg")

            manager.audible_client.download = AsyncMock(return_value={
                "success": True,
                "asin": asin,
                "title": title,
                "output_dir": str(settings.downloads_dir),
                "files": [aaxc_path, voucher_path, cover_path],
            })

            # Mock database session
            with patch("services.job_manager.get_session") as mock_get_session:
                mock_book = MagicMock()
                mock_book.asin = asin
                mock_book.title = title

                mock_session = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_book])))
                mock_result.scalar_one_or_none = MagicMock(return_value=mock_book)
                mock_session.execute = AsyncMock(return_value=mock_result)
                mock_session.add = MagicMock()
                mock_session.commit = AsyncMock()

                async def session_gen():
                    yield mock_session
                mock_get_session.return_value = session_gen()

                from uuid import uuid4
                job_id = uuid4()

                await manager._execute_download(job_id, [asin])

            # Manifest should now exist
            assert manifest_path.exists(), "Manifest should be created if it does not exist"

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert asin in manifest

    @pytest.mark.asyncio
    async def test_download_manifest_handles_corrupt_json(self, tmp_path: Path) -> None:
        """Verify corrupt manifest JSON is handled gracefully (starts fresh)."""
        with patch("services.job_manager.get_settings") as mock_settings:
            settings = self._create_mock_settings(tmp_path)
            mock_settings.return_value = settings

            # Create required directories
            settings.manifest_dir.mkdir(parents=True, exist_ok=True)
            settings.downloads_dir.mkdir(parents=True, exist_ok=True)

            # Create a corrupt manifest file
            manifest_path = settings.manifest_dir / "download_manifest.json"
            manifest_path.write_text("{ this is not valid json }", encoding="utf-8")

            manager = JobManager()
            manager.audible_client = MagicMock()

            asin = "B00RECOVER"
            title = "Recovery Book"
            aaxc_path = str(settings.downloads_dir / f"{asin}.aaxc")
            voucher_path = str(settings.downloads_dir / f"{asin}.voucher")
            cover_path = str(settings.downloads_dir / f"{asin}.jpg")

            manager.audible_client.download = AsyncMock(return_value={
                "success": True,
                "asin": asin,
                "title": title,
                "output_dir": str(settings.downloads_dir),
                "files": [aaxc_path, voucher_path, cover_path],
            })

            # Mock database session
            with patch("services.job_manager.get_session") as mock_get_session:
                mock_book = MagicMock()
                mock_book.asin = asin
                mock_book.title = title

                mock_session = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_book])))
                mock_result.scalar_one_or_none = MagicMock(return_value=mock_book)
                mock_session.execute = AsyncMock(return_value=mock_result)
                mock_session.add = MagicMock()
                mock_session.commit = AsyncMock()

                async def session_gen():
                    yield mock_session
                mock_get_session.return_value = session_gen()

                from uuid import uuid4
                job_id = uuid4()

                # This should NOT raise an exception
                await manager._execute_download(job_id, [asin])

            # Manifest should be valid JSON now
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert asin in manifest
            assert manifest[asin]["status"] == "success"
