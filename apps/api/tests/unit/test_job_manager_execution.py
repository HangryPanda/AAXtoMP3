"""Unit tests for JobManager execution logic."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Book, BookStatus, Job
from services.job_manager import JobManager


class TestJobManagerExecution:
    """Tests for JobManager execution methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create JobManager instance with mocked settings."""
        with patch("services.job_manager.get_settings") as mock_settings:
            settings = MagicMock()
            settings.max_download_concurrent = 2
            settings.max_convert_concurrent = 2
            settings.downloads_dir = tmp_path / "downloads"
            settings.converted_dir = tmp_path / "converted"
            settings.completed_dir = tmp_path / "completed"
            settings.manifest_dir = tmp_path / "specs"
            settings.data_dir = tmp_path / "data"
            settings.move_after_complete = False
            mock_settings.return_value = settings
            
            # Ensure directories exist
            settings.downloads_dir.mkdir(parents=True)
            settings.converted_dir.mkdir(parents=True)
            settings.completed_dir.mkdir(parents=True)
            settings.manifest_dir.mkdir(parents=True)
            settings.data_dir.mkdir(parents=True)

            mgr = JobManager()
            # Mock internal services
            mgr.audible_client = MagicMock()
            mgr.converter = MagicMock()
            mgr.metadata_extractor = MagicMock()
            mgr.library_manager = MagicMock()
            return mgr

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.mark.asyncio
    async def test_execute_download_success(self, manager, mock_session):
        """Test successful download execution."""
        job_id = uuid4()
        asins = ["B001", "B002"]
        
        # Mock audible client download
        manager.audible_client.download = AsyncMock(side_effect=[
            {"success": True, "asin": "B001", "files": ["/path/B001.aaxc"]},
            {"success": True, "asin": "B002", "files": ["/path/B002.aaxc"]}
        ])

        # Mock DB session context manager
        # Since _execute_download uses `async for session in get_session():`
        # we need to patch get_session to yield our mock session
        
        with patch("services.job_manager.get_session") as mock_get_session:
            async def yield_session():
                yield mock_session
            mock_get_session.side_effect = yield_session
            
            # Mock DB queries
            # 1. Fetch titles: return list of books
            mock_session.execute.side_effect = [
                # First execute: select(Book).where(Book.asin.in_(asins))
                MagicMock(scalars=lambda: MagicMock(all=lambda: [
                    Book(asin="B001", title="Title 1"),
                    Book(asin="B002", title="Title 2")
                ])),
                # Second execute: select(Job).where(Job.id == job_id)
                MagicMock(scalar_one_or_none=lambda: Job(id=job_id)),
                # Subsequent executes: select(Book).where(Book.asin == asin) inside loop
                MagicMock(scalar_one_or_none=lambda: Book(asin="B001", status=BookStatus.NEW)),
                MagicMock(scalar_one_or_none=lambda: Book(asin="B002", status=BookStatus.NEW)),
            ]

            result = await manager._execute_download(job_id, asins)

            assert result["success"] is True
            assert result["successful_count"] == 2
            assert manager.audible_client.download.call_count == 2
            
            # Verify DB updates were committed
            assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_execute_download_partial_failure(self, manager, mock_session):
        """Test download execution with mixed success/failure."""
        job_id = uuid4()
        asins = ["B001", "B002"]
        
        manager.audible_client.download = AsyncMock(side_effect=[
            {"success": True, "asin": "B001", "files": ["/path/B001.aaxc"]},
            {"success": False, "asin": "B002", "error": "Download failed"}
        ])

        with patch("services.job_manager.get_session") as mock_get_session:
            async def yield_session():
                yield mock_session
            mock_get_session.side_effect = yield_session
            
            # Mock DB queries
            mock_session.execute.side_effect = [
                # fetch titles
                MagicMock(scalars=lambda: MagicMock(all=lambda: [])),
                # fetch job
                MagicMock(scalar_one_or_none=lambda: Job(id=job_id)),
                # fetch book for success
                MagicMock(scalar_one_or_none=lambda: Book(asin="B001", status=BookStatus.NEW)),
            ]

            result = await manager._execute_download(job_id, asins)

            assert result["success"] is False  # Overall success false if any failed? 
            # Looking at code: success = all(r.get("success", False) for r in results) -> So YES, False.
            assert result["successful_count"] == 1
            assert result["total_count"] == 2

    @pytest.mark.asyncio
    async def test_execute_conversion_success(self, manager, mock_session, tmp_path):
        """Test successful conversion execution."""
        job_id = uuid4()
        asin = "B001"
        
        # Setup input file
        input_file = manager.settings.downloads_dir / "B001.aaxc"
        input_file.touch()
        
        # Mock converter
        manager.converter.convert = AsyncMock(return_value={
            "success": True, 
            "output_files": ["/path/out.m4b"]
        })
        
        # Mock library scan
        manager.library_manager.scan_book = AsyncMock(return_value=True)

        with patch("services.job_manager.get_session") as mock_get_session:
            async def yield_session():
                yield mock_session
            mock_get_session.side_effect = yield_session
            
            # Mock DB: 
            # 1. Look for book to find input file path (fallback to file system if not in DB, but let's test DB path)
            # 2. Update book after conversion
            book = Book(asin=asin, title="Test Title", local_path_aax=str(input_file))
            
            mock_session.execute.side_effect = [
                # First check for input file
                MagicMock(scalar_one_or_none=lambda: book),
                # Second check for update
                MagicMock(scalar_one_or_none=lambda: book),
            ]

            result = await manager._execute_conversion(job_id, asin, "m4b", None)

            assert result["success"] is True
            assert manager.converter.convert.called
            assert book.status == BookStatus.COMPLETED
            assert book.local_path_converted == "/path/out.m4b"
            assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_execute_conversion_input_not_found(self, manager, mock_session):
        """Test conversion failure when input file is missing."""
        job_id = uuid4()
        asin = "B00MISSING"
        
        # Ensure no files in downloads
        
        with patch("services.job_manager.get_session") as mock_get_session:
            async def yield_session():
                yield mock_session
            mock_get_session.side_effect = yield_session
            
            # DB returns book but path doesn't exist
            mock_session.execute.return_value = MagicMock(scalar_one_or_none=lambda: Book(asin=asin))

            result = await manager._execute_conversion(job_id, asin, "m4b", None)

            assert result["success"] is False
            assert result["error"] == "Input file not found"
            assert not manager.converter.convert.called

    @pytest.mark.asyncio
    async def test_execute_conversion_failure(self, manager, mock_session, tmp_path):
        """Test conversion failure during processing."""
        job_id = uuid4()
        asin = "B00FAIL"
        
        input_file = manager.settings.downloads_dir / "B00FAIL.aaxc"
        input_file.touch()
        
        manager.converter.convert = AsyncMock(return_value={
            "success": False, 
            "error": "Transcoding error"
        })

        with patch("services.job_manager.get_session") as mock_get_session:
            async def yield_session():
                yield mock_session
            mock_get_session.side_effect = yield_session
            
            mock_session.execute.return_value = MagicMock(scalar_one_or_none=lambda: Book(asin=asin))

            result = await manager._execute_conversion(job_id, asin, "m4b", None)

            assert result["success"] is False
            assert "Transcoding error" in str(result) # error logic might wrap it or return in dict
            
            # Verify book status NOT updated to COMPLETED
            # The code does not update DB status on failure in _execute_conversion currently?
            # Let's check logic: if result.get("success"): ... else: ...
            # The else block logs error but doesn't seem to update Book status to FAILED in DB explicitly inside _execute_conversion?
            # Re-reading code: Post-Processing (JobManager) doc says Failure -> FAILED.
            # But in `_execute_conversion`:
            # if result.get("success"): ...
            # else: self._update_converted_manifest(...)
            # It does NOT update Book DB status to FAILED. This might be a bug or intended to handle in caller?
            # But _execute_conversion is called via asyncio.create_task.
            
            # Wait, looking at `queue_conversion`, it just fires and forgets.
            # So if `_execute_conversion` doesn't update DB on failure, the book stays in CONVERTING (or whatever it was).
            # This confirms a potential logic gap to be tested!

    @pytest.mark.asyncio
    async def test_conversion_failure_updates_db_status(self, manager, mock_session, tmp_path):
        """
        Verify that a failed conversion updates the Book status to FAILED.
        """
        job_id = uuid4()
        asin = "B00FAIL123"
        
        # Create input file
        input_file = manager.settings.downloads_dir / "B00FAIL123.aaxc"
        input_file.write_bytes(b"content")

        # Mock converter to fail
        manager.converter.convert = AsyncMock(return_value={
            "success": False, 
            "error": "Transcoding failed",
            "stderr": "Serious ffmpeg error"
        })
        
        # Setup book object
        book = Book(asin=asin, title="Fail Book", status=BookStatus.NEW)
        
        with patch("services.job_manager.get_session") as mock_get_session:
            async def yield_session():
                yield mock_session
            mock_get_session.side_effect = lambda: yield_session()
            
            # Mock DB behavior
            mock_session.execute.side_effect = [
                MagicMock(scalar_one_or_none=lambda: book),  # 1. Fetch to find file
                MagicMock(scalar_one_or_none=lambda: book),  # 2. Fetch to update status
            ]

            await manager._execute_conversion(job_id, asin, "m4b", None)

            # Assertions
            assert book.status == BookStatus.FAILED, f"Book status should be FAILED, but was {book.status}"
            assert mock_session.commit.called, "Session commit should be called to save status change"
