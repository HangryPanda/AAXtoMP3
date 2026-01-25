"""Integration tests for job management endpoints."""

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Book, BookStatus, Job, JobStatus, JobType


class TestJobEndpoints:
    """Tests for job management endpoints."""

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, client: AsyncClient) -> None:
        """Test listing jobs when none exist."""
        response = await client.get("/jobs")

        assert response.status_code == 200
        data = response.json()

        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_jobs_with_data(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test listing jobs with data in database."""
        # Create jobs
        job1 = Job(task_type=JobType.DOWNLOAD, status=JobStatus.PENDING)
        job2 = Job(task_type=JobType.CONVERT, status=JobStatus.COMPLETED)
        test_session.add_all([job1, job2])
        await test_session.commit()

        response = await client.get("/jobs")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_status(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test filtering jobs by status."""
        job1 = Job(task_type=JobType.DOWNLOAD, status=JobStatus.PENDING)
        job2 = Job(task_type=JobType.DOWNLOAD, status=JobStatus.COMPLETED)
        job3 = Job(task_type=JobType.CONVERT, status=JobStatus.PENDING)
        test_session.add_all([job1, job2, job3])
        await test_session.commit()

        response = await client.get("/jobs?status=PENDING")
        data = response.json()

        assert data["total"] == 2
        for item in data["items"]:
            assert item["status"] == "PENDING"

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_task_type(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test filtering jobs by task type."""
        job1 = Job(task_type=JobType.DOWNLOAD, status=JobStatus.PENDING)
        job2 = Job(task_type=JobType.CONVERT, status=JobStatus.PENDING)
        job3 = Job(task_type=JobType.CONVERT, status=JobStatus.COMPLETED)
        test_session.add_all([job1, job2, job3])
        await test_session.commit()

        response = await client.get("/jobs?task_type=CONVERT")
        data = response.json()

        assert data["total"] == 2
        for item in data["items"]:
            assert item["task_type"] == "CONVERT"

    @pytest.mark.asyncio
    async def test_list_jobs_combined_filters(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test filtering jobs by both status and task type."""
        job1 = Job(task_type=JobType.DOWNLOAD, status=JobStatus.PENDING)
        job2 = Job(task_type=JobType.CONVERT, status=JobStatus.PENDING)
        job3 = Job(task_type=JobType.CONVERT, status=JobStatus.COMPLETED)
        test_session.add_all([job1, job2, job3])
        await test_session.commit()

        response = await client.get("/jobs?status=PENDING&task_type=CONVERT")
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["task_type"] == "CONVERT"
        assert data["items"][0]["status"] == "PENDING"

    @pytest.mark.asyncio
    async def test_list_jobs_limit(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test limiting number of returned jobs."""
        for i in range(10):
            job = Job(task_type=JobType.DOWNLOAD, status=JobStatus.PENDING)
            test_session.add(job)
        await test_session.commit()

        response = await client.get("/jobs?limit=5")
        data = response.json()

        assert len(data["items"]) == 5

    @pytest.mark.asyncio
    async def test_get_job_by_id(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test getting a specific job by ID."""
        job = Job(
            task_type=JobType.DOWNLOAD,
            book_asin="B00TEST123",
            status=JobStatus.RUNNING,
            progress_percent=50,
        )
        test_session.add(job)
        await test_session.commit()
        await test_session.refresh(job)

        response = await client.get(f"/jobs/{job.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(job.id)
        assert data["task_type"] == "DOWNLOAD"
        assert data["status"] == "RUNNING"
        assert data["progress_percent"] == 50
        assert data["book_asin"] == "B00TEST123"

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, client: AsyncClient) -> None:
        """Test getting a non-existent job."""
        fake_uuid = "12345678-1234-5678-1234-567812345678"
        response = await client.get(f"/jobs/{fake_uuid}")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


class TestDownloadJobEndpoint:
    """Tests for POST /jobs/download endpoint."""

    @pytest.mark.asyncio
    async def test_create_download_job_single_asin(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test creating a download job with single ASIN."""
        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.queue_download = AsyncMock()

            response = await client.post(
                "/jobs/download",
                json={"asin": "B00TEST123"},
            )

            assert response.status_code == 202
            data = response.json()

            assert "job_id" in data
            assert data["status"] == "QUEUED"
            assert "queued" in data["message"].lower()

            # Verify job was queued
            mock_manager.queue_download.assert_called_once()
            call_args = mock_manager.queue_download.call_args
            assert call_args.args[1] == ["B00TEST123"]

    @pytest.mark.asyncio
    async def test_create_download_job_batch_asins(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test creating a download job with multiple ASINs (batch)."""
        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.queue_download = AsyncMock()

            asins = ["B00TEST001", "B00TEST002", "B00TEST003"]
            response = await client.post(
                "/jobs/download",
                json={"asins": asins},
            )

            assert response.status_code == 202
            data = response.json()

            assert "job_ids" in data
            assert len(data["job_ids"]) == 3
            assert data["status"] == "QUEUED"
            assert "3 item" in data["message"]

            # Batch is queued as multiple jobs (one per ASIN).
            assert mock_manager.queue_download.call_count == 3
            queued_asins = [c.args[1][0] for c in mock_manager.queue_download.call_args_list]
            assert queued_asins == asins

    @pytest.mark.asyncio
    async def test_create_download_job_no_asin(
        self,
        client: AsyncClient,
    ) -> None:
        """Test creating a download job without ASIN returns 400."""
        response = await client.post(
            "/jobs/download",
            json={},
        )

        assert response.status_code == 400
        data = response.json()
        assert "asin" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_download_job_empty_asins_list(
        self,
        client: AsyncClient,
    ) -> None:
        """Test creating a download job with empty ASINs list returns 400."""
        response = await client.post(
            "/jobs/download",
            json={"asins": []},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_download_job_creates_db_record(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test that download job creates database record."""
        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.queue_download = AsyncMock()

            response = await client.post(
                "/jobs/download",
                json={"asin": "B00TEST123"},
            )

            assert response.status_code == 202
            job_id = response.json()["job_id"]

            # Verify job exists in database
            get_response = await client.get(f"/jobs/{job_id}")
            assert get_response.status_code == 200

            job_data = get_response.json()
            assert job_data["task_type"] == "DOWNLOAD"


class TestConvertJobEndpoint:
    """Tests for POST /jobs/convert endpoint."""

    @pytest.mark.asyncio
    async def test_create_convert_job(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test creating a conversion job."""
        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.queue_conversion = AsyncMock()

            response = await client.post(
                "/jobs/convert",
                json={"asin": "B00TEST123"},
            )

            assert response.status_code == 202
            data = response.json()

            assert "job_id" in data
            assert data["status"] == "QUEUED"

            mock_manager.queue_conversion.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_convert_job_with_format(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test creating a conversion job with format option."""
        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.queue_conversion = AsyncMock()

            response = await client.post(
                "/jobs/convert",
                json={"asin": "B00TEST123", "format": "mp3"},
            )

            assert response.status_code == 202

            # Verify format was passed
            call_args = mock_manager.queue_conversion.call_args
            assert call_args.kwargs["format"] == "mp3"

    @pytest.mark.asyncio
    async def test_create_convert_job_with_naming_scheme(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test creating a conversion job with naming scheme."""
        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.queue_conversion = AsyncMock()

            response = await client.post(
                "/jobs/convert",
                json={
                    "asin": "B00TEST123",
                    "naming_scheme": "$artist/$title",
                },
            )

            assert response.status_code == 202

            # Verify naming scheme was passed
            call_args = mock_manager.queue_conversion.call_args
            assert call_args.kwargs["naming_scheme"] == "$artist/$title"

    @pytest.mark.asyncio
    async def test_create_convert_job_no_asin(
        self,
        client: AsyncClient,
    ) -> None:
        """Test creating a conversion job without ASIN returns 400."""
        response = await client.post(
            "/jobs/convert",
            json={"format": "mp3"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "asin" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_convert_job_default_format(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test conversion job uses m4b as default format."""
        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.queue_conversion = AsyncMock()

            response = await client.post(
                "/jobs/convert",
                json={"asin": "B00TEST123"},
            )

            assert response.status_code == 202

            # Verify default format was used
            call_args = mock_manager.queue_conversion.call_args
            assert call_args.kwargs["format"] == "m4b"


class TestCancelJobEndpoint:
    """Tests for DELETE /jobs/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_cancel_pending_job(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test cancelling a pending job."""
        job = Job(task_type=JobType.DOWNLOAD, status=JobStatus.PENDING)
        test_session.add(job)
        await test_session.commit()
        await test_session.refresh(job)

        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.cancel_job = AsyncMock(return_value=True)

            response = await client.delete(f"/jobs/{job.id}")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "cancelled"
            mock_manager.cancel_job.assert_called_once_with(job.id)

    @pytest.mark.asyncio
    async def test_cancel_running_job(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test cancelling a running job."""
        job = Job(task_type=JobType.CONVERT, status=JobStatus.RUNNING)
        test_session.add(job)
        await test_session.commit()
        await test_session.refresh(job)

        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.cancel_job = AsyncMock(return_value=True)

            response = await client.delete(f"/jobs/{job.id}")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_already_completed_job(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test cancelling an already completed job returns appropriate status."""
        job = Job(task_type=JobType.DOWNLOAD, status=JobStatus.COMPLETED)
        test_session.add(job)
        await test_session.commit()
        await test_session.refresh(job)

        response = await client.delete(f"/jobs/{job.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "already_completed"

    @pytest.mark.asyncio
    async def test_cancel_already_failed_job(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test cancelling an already failed job returns appropriate status."""
        job = Job(task_type=JobType.DOWNLOAD, status=JobStatus.FAILED)
        test_session.add(job)
        await test_session.commit()
        await test_session.refresh(job)

        response = await client.delete(f"/jobs/{job.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "already_completed"

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled_job(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test cancelling an already cancelled job returns appropriate status."""
        job = Job(task_type=JobType.DOWNLOAD, status=JobStatus.CANCELLED)
        test_session.add(job)
        await test_session.commit()
        await test_session.refresh(job)

        response = await client.delete(f"/jobs/{job.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "already_completed"

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(
        self,
        client: AsyncClient,
    ) -> None:
        """Test cancelling a non-existent job."""
        fake_uuid = "12345678-1234-5678-1234-567812345678"

        response = await client.delete(f"/jobs/{fake_uuid}")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_cancel_job_updates_status(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test that cancelling a job updates its status in database."""
        job = Job(task_type=JobType.DOWNLOAD, status=JobStatus.PENDING)
        test_session.add(job)
        await test_session.commit()
        await test_session.refresh(job)

        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.cancel_job = AsyncMock(return_value=True)

            await client.delete(f"/jobs/{job.id}")

            # Verify job status was updated
            get_response = await client.get(f"/jobs/{job.id}")
            job_data = get_response.json()

            assert job_data["status"] == "CANCELLED"
            assert job_data["completed_at"] is not None


class TestRetryJobEndpoint:
    """Tests for POST /jobs/{id}/retry endpoint."""

    @pytest.mark.asyncio
    async def test_retry_failed_download_job(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test retrying a failed download job."""
        import json

        job = Job(
            task_type=JobType.DOWNLOAD,
            book_asin="B00TEST123",
            status=JobStatus.FAILED,
            payload_json=json.dumps({"asins": ["B00TEST123"]}),
        )
        test_session.add(job)
        await test_session.commit()
        await test_session.refresh(job)

        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.queue_download = AsyncMock()

            response = await client.post(f"/jobs/{job.id}/retry")

            assert response.status_code == 202
            data = response.json()

            assert "job_id" in data
            assert data["status"] == "QUEUED"
            assert "attempt #2" in data["message"]

            # Verify new job was queued
            mock_manager.queue_download.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_failed_convert_job(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test retrying a failed conversion job."""
        import json

        job = Job(
            task_type=JobType.CONVERT,
            book_asin="B00TEST123",
            status=JobStatus.FAILED,
            payload_json=json.dumps({"asin": "B00TEST123", "format": "m4b"}),
        )
        test_session.add(job)
        await test_session.commit()
        await test_session.refresh(job)

        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.queue_conversion = AsyncMock()

            response = await client.post(f"/jobs/{job.id}/retry")

            assert response.status_code == 202
            data = response.json()

            assert "job_id" in data
            assert data["status"] == "QUEUED"
            assert "attempt #2" in data["message"]

            mock_manager.queue_conversion.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_job_increments_attempt(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test that retrying a job increments the attempt number."""
        import json

        # Create a job that's already attempt 2
        job = Job(
            task_type=JobType.CONVERT,
            book_asin="B00TEST123",
            status=JobStatus.FAILED,
            payload_json=json.dumps({"asin": "B00TEST123", "format": "m4b"}),
            attempt=2,
        )
        test_session.add(job)
        await test_session.commit()
        await test_session.refresh(job)

        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.queue_conversion = AsyncMock()

            response = await client.post(f"/jobs/{job.id}/retry")

            assert response.status_code == 202
            data = response.json()

            # Should be attempt #3
            assert "attempt #3" in data["message"]

            # Verify the new job has correct attempt number
            new_job_id = data["job_id"]
            get_response = await client.get(f"/jobs/{new_job_id}")
            new_job_data = get_response.json()

            assert new_job_data["attempt"] == 3
            assert new_job_data["original_job_id"] == str(job.id)

    @pytest.mark.asyncio
    async def test_retry_job_sets_original_job_id(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test that retrying a job sets the original_job_id."""
        import json

        original_job = Job(
            task_type=JobType.CONVERT,
            book_asin="B00TEST123",
            status=JobStatus.FAILED,
            payload_json=json.dumps({"asin": "B00TEST123", "format": "m4b"}),
        )
        test_session.add(original_job)
        await test_session.commit()
        await test_session.refresh(original_job)

        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.queue_conversion = AsyncMock()

            response = await client.post(f"/jobs/{original_job.id}/retry")

            assert response.status_code == 202
            new_job_id = response.json()["job_id"]

            # Verify the new job links back to original
            get_response = await client.get(f"/jobs/{new_job_id}")
            new_job_data = get_response.json()

            assert new_job_data["original_job_id"] == str(original_job.id)

    @pytest.mark.asyncio
    async def test_retry_retried_job_links_to_original(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test that retrying a retry still links to the original job."""
        import json
        from uuid import uuid4

        # Create the original job
        original_id = uuid4()

        # Create a retry of that job (attempt 2)
        retry_job = Job(
            task_type=JobType.CONVERT,
            book_asin="B00TEST123",
            status=JobStatus.FAILED,
            payload_json=json.dumps({"asin": "B00TEST123", "format": "m4b"}),
            attempt=2,
            original_job_id=original_id,
        )
        test_session.add(retry_job)
        await test_session.commit()
        await test_session.refresh(retry_job)

        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.queue_conversion = AsyncMock()

            response = await client.post(f"/jobs/{retry_job.id}/retry")

            assert response.status_code == 202
            new_job_id = response.json()["job_id"]

            # Verify the new job (attempt 3) still links to original, not to retry_job
            get_response = await client.get(f"/jobs/{new_job_id}")
            new_job_data = get_response.json()

            assert new_job_data["attempt"] == 3
            assert new_job_data["original_job_id"] == str(original_id)

    @pytest.mark.asyncio
    async def test_retry_active_job_fails(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test that retrying an active job returns 409."""
        import json

        job = Job(
            task_type=JobType.CONVERT,
            book_asin="B00TEST123",
            status=JobStatus.RUNNING,
            payload_json=json.dumps({"asin": "B00TEST123", "format": "m4b"}),
        )
        test_session.add(job)
        await test_session.commit()
        await test_session.refresh(job)

        response = await client.post(f"/jobs/{job.id}/retry")

        assert response.status_code == 409
        assert "still active" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_retry_nonexistent_job(
        self,
        client: AsyncClient,
    ) -> None:
        """Test retrying a non-existent job returns 404."""
        fake_uuid = "12345678-1234-5678-1234-567812345678"

        response = await client.post(f"/jobs/{fake_uuid}/retry")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_job_response_includes_retry_fields(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test that job response includes attempt and original_job_id fields."""
        from uuid import uuid4

        original_id = uuid4()
        job = Job(
            task_type=JobType.CONVERT,
            book_asin="B00TEST123",
            status=JobStatus.COMPLETED,
            attempt=2,
            original_job_id=original_id,
        )
        test_session.add(job)
        await test_session.commit()
        await test_session.refresh(job)

        response = await client.get(f"/jobs/{job.id}")

        assert response.status_code == 200
        data = response.json()

        assert "attempt" in data
        assert data["attempt"] == 2
        assert "original_job_id" in data
        assert data["original_job_id"] == str(original_id)
