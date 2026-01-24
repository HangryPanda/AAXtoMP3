"""Unit tests for JobManager service."""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from services.job_manager import JobManager


class TestJobManagerInit:
    """Tests for JobManager initialization."""

    def test_init_creates_semaphores(self) -> None:
        """Test that manager initializes with semaphores."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()

            assert manager.download_semaphore._value == 5
            assert manager.convert_semaphore._value == 2

    def test_init_starts_with_empty_tasks(self) -> None:
        """Test that manager starts with no tasks."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()

            assert len(manager._tasks) == 0
            assert len(manager._cancelled) == 0


class TestQueueDownload:
    """Tests for queue_download method."""

    @pytest.mark.asyncio
    async def test_queue_download_creates_task(self) -> None:
        """Test that queuing download creates an asyncio task."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()
            manager.audible_client = MagicMock()
            manager.audible_client.download = AsyncMock(return_value={"success": True})

            job_id = uuid4()
            await manager.queue_download(job_id, ["B00TEST123"])

            assert job_id in manager._tasks
            assert manager._tasks[job_id].get_name() == f"download-{job_id}"

            # Clean up
            await manager.cancel_job(job_id)

    @pytest.mark.asyncio
    async def test_queue_download_with_callback(self) -> None:
        """Test queuing download with progress callback."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()
            manager.audible_client = MagicMock()
            manager.audible_client.download = AsyncMock(return_value={"success": True})

            progress_calls: list[tuple[int, str]] = []

            def callback(percent: int, line: str) -> None:
                progress_calls.append((percent, line))

            job_id = uuid4()
            await manager.queue_download(job_id, ["B00TEST123"], progress_callback=callback)

            assert job_id in manager._progress_callbacks

            # Clean up
            await manager.cancel_job(job_id)


class TestQueueConversion:
    """Tests for queue_conversion method."""

    @pytest.mark.asyncio
    async def test_queue_conversion_creates_task(self) -> None:
        """Test that queuing conversion creates an asyncio task."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()
            # Mock to prevent actual execution
            manager._execute_conversion = AsyncMock(return_value={"success": True})

            job_id = uuid4()
            await manager.queue_conversion(job_id, "B00TEST123")

            assert job_id in manager._tasks
            assert manager._tasks[job_id].get_name() == f"convert-{job_id}"

            # Clean up
            await manager.cancel_job(job_id)

    @pytest.mark.asyncio
    async def test_queue_conversion_with_format(self) -> None:
        """Test queuing conversion with specific format."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()

            call_args: dict[str, Any] = {}

            async def capture_args(
                job_id: UUID, asin: str, format: str, naming_scheme: str | None
            ) -> dict[str, Any]:
                call_args["format"] = format
                return {"success": True}

            manager._execute_conversion = capture_args  # type: ignore

            job_id = uuid4()
            await manager.queue_conversion(job_id, "B00TEST123", format="mp3")

            # Wait a tiny bit for task to start
            await asyncio.sleep(0.01)

            assert call_args.get("format") == "mp3"

            # Clean up
            await manager.cancel_job(job_id)


class TestCancelJob:
    """Tests for cancel_job method."""

    @pytest.mark.asyncio
    async def test_cancel_job_success(self) -> None:
        """Test successfully cancelling a job."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()

            # Create a slow task that can be cancelled
            async def slow_task() -> dict[str, Any]:
                await asyncio.sleep(10)
                return {"success": True}

            job_id = uuid4()
            manager._tasks[job_id] = asyncio.create_task(slow_task())

            result = await manager.cancel_job(job_id)

            assert result is True
            assert job_id not in manager._tasks

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self) -> None:
        """Test cancelling a non-existent job returns False."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()

            result = await manager.cancel_job(uuid4())

            assert result is False

    @pytest.mark.asyncio
    async def test_cancel_job_removes_callback(self) -> None:
        """Test cancelling a job removes its progress callback."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()

            job_id = uuid4()
            manager._progress_callbacks[job_id] = lambda p, l: None
            manager._tasks[job_id] = asyncio.create_task(asyncio.sleep(10))

            await manager.cancel_job(job_id)

            assert job_id not in manager._progress_callbacks


class TestIsCancelled:
    """Tests for is_cancelled method."""

    def test_is_cancelled_returns_false_for_active_job(self) -> None:
        """Test is_cancelled returns False for non-cancelled job."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()
            job_id = uuid4()

            assert manager.is_cancelled(job_id) is False

    def test_is_cancelled_returns_true_for_cancelled_job(self) -> None:
        """Test is_cancelled returns True for cancelled job."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()
            job_id = uuid4()
            manager._cancelled.add(job_id)

            assert manager.is_cancelled(job_id) is True


class TestGetRunningCount:
    """Tests for get_running_count method."""

    def test_get_running_count_empty(self) -> None:
        """Test running count when no jobs are running."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()

            counts = manager.get_running_count()

            assert counts["downloads"] == 0
            assert counts["conversions"] == 0
            assert counts["total"] == 0

    @pytest.mark.asyncio
    async def test_get_running_count_with_jobs(self) -> None:
        """Test running count with active jobs."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()

            # Create mock tasks
            download_id = uuid4()
            convert_id = uuid4()

            download_task = asyncio.create_task(
                asyncio.sleep(10), name=f"download-{download_id}"
            )
            convert_task = asyncio.create_task(
                asyncio.sleep(10), name=f"convert-{convert_id}"
            )

            manager._tasks[download_id] = download_task
            manager._tasks[convert_id] = convert_task

            counts = manager.get_running_count()

            assert counts["downloads"] == 1
            assert counts["conversions"] == 1
            assert counts["total"] == 2

            # Clean up
            download_task.cancel()
            convert_task.cancel()
            try:
                await download_task
            except asyncio.CancelledError:
                pass
            try:
                await convert_task
            except asyncio.CancelledError:
                pass


class TestSemaphoreLimits:
    """Tests for semaphore-based concurrency limits."""

    @pytest.mark.asyncio
    async def test_download_semaphore_limits_concurrent(self) -> None:
        """Test download semaphore limits concurrent downloads."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=2,  # Only 2 concurrent
                max_convert_concurrent=2,
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()

            concurrent_count = 0
            max_concurrent = 0
            completed: list[UUID] = []

            async def track_download(job_id: UUID, asins: list[str]) -> dict[str, Any]:
                nonlocal concurrent_count, max_concurrent
                async with manager.download_semaphore:
                    concurrent_count += 1
                    max_concurrent = max(max_concurrent, concurrent_count)
                    await asyncio.sleep(0.05)
                    concurrent_count -= 1
                    completed.append(job_id)
                    return {"success": True}

            manager._execute_download = track_download  # type: ignore

            # Queue 5 downloads
            job_ids = [uuid4() for _ in range(5)]
            for job_id in job_ids:
                await manager.queue_download(job_id, ["B00TEST"])

            # Wait for all to complete
            await asyncio.sleep(0.5)

            # Should never have exceeded limit of 2
            assert max_concurrent <= 2
            # All should have completed
            assert len(completed) == 5

    @pytest.mark.asyncio
    async def test_convert_semaphore_limits_concurrent(self) -> None:
        """Test convert semaphore limits concurrent conversions."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=1,  # Only 1 concurrent
                downloads_dir=Path("/downloads"),
                converted_dir=Path("/converted"),
                completed_dir=Path("/completed"),
            )

            manager = JobManager()

            concurrent_count = 0
            max_concurrent = 0
            completed: list[UUID] = []

            async def track_convert(
                job_id: UUID,
                asin: str,
                format: str,
                naming_scheme: str | None,
            ) -> dict[str, Any]:
                nonlocal concurrent_count, max_concurrent
                async with manager.convert_semaphore:
                    concurrent_count += 1
                    max_concurrent = max(max_concurrent, concurrent_count)
                    await asyncio.sleep(0.05)
                    concurrent_count -= 1
                    completed.append(job_id)
                    return {"success": True}

            manager._execute_conversion = track_convert  # type: ignore

            # Queue 3 conversions
            job_ids = [uuid4() for _ in range(3)]
            for job_id in job_ids:
                await manager.queue_conversion(job_id, "B00TEST")

            # Wait for all to complete
            await asyncio.sleep(0.3)

            # Should never have exceeded limit of 1
            assert max_concurrent <= 1
            assert len(completed) == 3


class TestFindInputFile:
    """Tests for _find_input_file method."""

    def test_find_input_file_aaxc(self, tmp_path: Path) -> None:
        """Test finding AAXC file in downloads directory."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=tmp_path,
                converted_dir=tmp_path / "converted",
                completed_dir=tmp_path / "completed",
            )

            manager = JobManager()

            # Create test file
            aaxc_file = tmp_path / "B00TEST123_TITLE.aaxc"
            aaxc_file.write_bytes(b"content")

            result = manager._find_input_file("B00TEST123")

            assert result is not None
            assert result.suffix == ".aaxc"

    def test_find_input_file_aax(self, tmp_path: Path) -> None:
        """Test finding AAX file in downloads directory."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=tmp_path,
                converted_dir=tmp_path / "converted",
                completed_dir=tmp_path / "completed",
            )

            manager = JobManager()

            # Create test file
            aax_file = tmp_path / "B00TEST123_TITLE.aax"
            aax_file.write_bytes(b"content")

            result = manager._find_input_file("B00TEST123")

            assert result is not None
            assert result.suffix == ".aax"

    def test_find_input_file_prefers_aaxc(self, tmp_path: Path) -> None:
        """Test that AAXC is preferred over AAX."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=tmp_path,
                converted_dir=tmp_path / "converted",
                completed_dir=tmp_path / "completed",
            )

            manager = JobManager()

            # Create both files
            (tmp_path / "B00TEST123.aax").write_bytes(b"aax")
            (tmp_path / "B00TEST123.aaxc").write_bytes(b"aaxc")

            result = manager._find_input_file("B00TEST123")

            assert result is not None
            assert result.suffix == ".aaxc"

    def test_find_input_file_not_found(self, tmp_path: Path) -> None:
        """Test returns None when file not found."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=tmp_path,
                converted_dir=tmp_path / "converted",
                completed_dir=tmp_path / "completed",
            )

            manager = JobManager()

            result = manager._find_input_file("NONEXISTENT")

            assert result is None

    def test_find_input_file_in_completed_dir(self, tmp_path: Path) -> None:
        """Test finding file in completed directory."""
        with patch("services.job_manager.get_settings") as mock_settings:
            completed_dir = tmp_path / "completed"
            completed_dir.mkdir()

            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=tmp_path / "downloads",
                converted_dir=tmp_path / "converted",
                completed_dir=completed_dir,
            )

            manager = JobManager()

            # Create file in completed subdirectory
            sub_dir = completed_dir / "Author" / "Title"
            sub_dir.mkdir(parents=True)
            aaxc_file = sub_dir / "B00TEST123_TITLE.aaxc"
            aaxc_file.write_bytes(b"content")

            result = manager._find_input_file("B00TEST123")

            assert result is not None
            assert "B00TEST123" in result.name


class TestExecuteDownload:
    """Tests for _execute_download method."""

    @pytest.mark.asyncio
    async def test_execute_download_single_asin(self, tmp_path: Path) -> None:
        """Test executing download for single ASIN."""
        with patch("services.job_manager.get_settings") as mock_settings:
            # Ensure dirs exist
            (tmp_path / "downloads").mkdir()
            (tmp_path / "converted").mkdir()
            (tmp_path / "completed").mkdir()
            (tmp_path / "specs").mkdir()

            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=tmp_path / "downloads",
                converted_dir=tmp_path / "converted",
                completed_dir=tmp_path / "completed",
                manifest_dir=tmp_path / "specs",
            )

            manager = JobManager()
            manager.audible_client = MagicMock()
            manager.audible_client.download = AsyncMock(
                return_value={"success": True, "asin": "B00TEST123"}
            )

            # Mock DB
            with patch("services.job_manager.get_session") as mock_get_session:
                mock_session = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                mock_result.scalars.return_value.all.return_value = [] # Fix for "coroutine object has no attribute all" warning
                mock_session.execute.return_value = mock_result
                
                async def session_gen():
                    yield mock_session
                mock_get_session.side_effect = session_gen

                job_id = uuid4()
                result = await manager._execute_download(job_id, ["B00TEST123"])

            assert result["success"] is True
            manager.audible_client.download.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_download_multiple_asins(self, tmp_path: Path) -> None:
        """Test executing download for multiple ASINs."""
        with patch("services.job_manager.get_settings") as mock_settings:
            (tmp_path / "downloads").mkdir()
            (tmp_path / "converted").mkdir()
            (tmp_path / "completed").mkdir()
            (tmp_path / "specs").mkdir()

            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=tmp_path / "downloads",
                converted_dir=tmp_path / "converted",
                completed_dir=tmp_path / "completed",
                manifest_dir=tmp_path / "specs",
            )

            manager = JobManager()
            manager.audible_client = MagicMock()
            manager.audible_client.download = AsyncMock(
                return_value={"success": True}
            )

            with patch("services.job_manager.get_session") as mock_get_session:
                mock_session = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                mock_result.scalars.return_value.all.return_value = []
                mock_session.execute.return_value = mock_result
                
                async def session_gen():
                    yield mock_session
                mock_get_session.side_effect = session_gen

                job_id = uuid4()
                result = await manager._execute_download(
                    job_id, ["B001", "B002", "B003"]
                )

            assert result["success"] is True
            assert manager.audible_client.download.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_download_cancelled(self, tmp_path: Path) -> None:
        """Test download returns early when cancelled."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=tmp_path,
                converted_dir=tmp_path / "converted",
                completed_dir=tmp_path / "completed",
            )

            manager = JobManager()
            job_id = uuid4()
            manager._cancelled.add(job_id)

            result = await manager._execute_download(job_id, ["B00TEST123"])

            assert result["success"] is False
            assert result["cancelled"] is True

    @pytest.mark.asyncio
    async def test_execute_download_with_callback(self, tmp_path: Path) -> None:
        """Test download calls progress callback."""
        with patch("services.job_manager.get_settings") as mock_settings:
            (tmp_path / "downloads").mkdir()
            (tmp_path / "converted").mkdir()
            (tmp_path / "completed").mkdir()
            (tmp_path / "specs").mkdir()

            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=tmp_path / "downloads",
                converted_dir=tmp_path / "converted",
                completed_dir=tmp_path / "completed",
                manifest_dir=tmp_path / "specs",
            )

            manager = JobManager()
            manager.audible_client = MagicMock()
            manager.audible_client.download = AsyncMock(
                return_value={"success": True}
            )

            progress_calls: list[tuple[int, str]] = []

            def callback(percent: int, line: str) -> None:
                progress_calls.append((percent, line))

            job_id = uuid4()
            manager._progress_callbacks[job_id] = callback

            with patch("services.job_manager.get_session") as mock_get_session:
                mock_session = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                mock_result.scalars.return_value.all.return_value = []
                mock_session.execute.return_value = mock_result
                
                async def session_gen():
                    yield mock_session
                mock_get_session.side_effect = session_gen

                await manager._execute_download(job_id, ["B001", "B002"])

            # Should have progress updates and completion
            assert len(progress_calls) >= 2
            assert any(p == 100 for p, _ in progress_calls)  # Final progress should be reached


class TestExecuteConversion:
    """Tests for _execute_conversion method."""

    @pytest.mark.asyncio
    async def test_execute_conversion_file_not_found(self, tmp_path: Path) -> None:
        """Test conversion fails when input file not found."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=tmp_path,
                converted_dir=tmp_path / "converted",
                completed_dir=tmp_path / "completed",
            )

            manager = JobManager()

            job_id = uuid4()
            result = await manager._execute_conversion(
                job_id, "NONEXISTENT", "m4b", None
            )

            assert result["success"] is False
            assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_conversion_success(self, tmp_path: Path) -> None:
        """Test successful conversion."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=tmp_path,
                converted_dir=tmp_path / "converted",
                completed_dir=tmp_path / "completed",
            )

            manager = JobManager()

            # Create input file
            (tmp_path / "B00TEST123.aaxc").write_bytes(b"content")

            manager.converter = MagicMock()
            manager.converter.convert = AsyncMock(
                return_value={"success": True, "returncode": 0}
            )

            job_id = uuid4()
            result = await manager._execute_conversion(
                job_id, "B00TEST123", "m4b", None
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_conversion_cancelled(self, tmp_path: Path) -> None:
        """Test conversion returns early when cancelled."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=tmp_path,
                converted_dir=tmp_path / "converted",
                completed_dir=tmp_path / "completed",
            )

            manager = JobManager()
            job_id = uuid4()
            manager._cancelled.add(job_id)

            result = await manager._execute_conversion(
                job_id, "B00TEST123", "m4b", None
            )

            assert result["success"] is False
            assert result["cancelled"] is True

    @pytest.mark.asyncio
    async def test_execute_conversion_with_voucher(self, tmp_path: Path) -> None:
        """Test conversion uses voucher file for AAXC."""
        with patch("services.job_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_download_concurrent=5,
                max_convert_concurrent=2,
                downloads_dir=tmp_path,
                converted_dir=tmp_path / "converted",
                completed_dir=tmp_path / "completed",
            )

            manager = JobManager()

            # Create input and voucher files
            (tmp_path / "B00TEST123.aaxc").write_bytes(b"content")
            (tmp_path / "B00TEST123.voucher").write_text("{}")

            manager.converter = MagicMock()
            manager.converter.convert = AsyncMock(
                return_value={"success": True, "returncode": 0}
            )

            job_id = uuid4()
            await manager._execute_conversion(job_id, "B00TEST123", "m4b", None)

            # Verify voucher was passed
            call_kwargs = manager.converter.convert.call_args.kwargs
            assert call_kwargs["voucher_file"] is not None
            assert "voucher" in str(call_kwargs["voucher_file"])
