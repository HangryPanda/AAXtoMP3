"""Integration tests for audio streaming endpoints."""

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Book, BookStatus


class TestStreamEndpoints:
    """Tests for audio streaming endpoints."""

    @pytest.mark.asyncio
    async def test_stream_audio_success(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test streaming audio for a completed book."""
        # Create a temporary audio file
        audio_file = tmp_path / "test_audio.m4b"
        audio_file.write_bytes(b"fake audio content for testing")

        # Create book with completed status
        book = Book(
            asin="B00STREAM01",
            title="Test Audiobook",
            status=BookStatus.COMPLETED,
            local_path_converted=str(audio_file),
            conversion_format="m4b",
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00STREAM01")

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mp4"
        assert "accept-ranges" in response.headers
        assert response.headers["accept-ranges"] == "bytes"

    @pytest.mark.asyncio
    async def test_stream_audio_mp3_format(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test streaming MP3 audio returns correct content type."""
        audio_file = tmp_path / "test_audio.mp3"
        audio_file.write_bytes(b"fake mp3 content")

        book = Book(
            asin="B00MP3TEST",
            title="MP3 Audiobook",
            status=BookStatus.COMPLETED,
            local_path_converted=str(audio_file),
            conversion_format="mp3",
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00MP3TEST")

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"

    @pytest.mark.asyncio
    async def test_stream_audio_flac_format(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test streaming FLAC audio returns correct content type."""
        audio_file = tmp_path / "test_audio.flac"
        audio_file.write_bytes(b"fake flac content")

        book = Book(
            asin="B00FLACTEST",
            title="FLAC Audiobook",
            status=BookStatus.COMPLETED,
            local_path_converted=str(audio_file),
            conversion_format="flac",
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00FLACTEST")

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/flac"

    @pytest.mark.asyncio
    async def test_stream_audio_opus_format(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test streaming Opus audio returns correct content type."""
        audio_file = tmp_path / "test_audio.opus"
        audio_file.write_bytes(b"fake opus content")

        book = Book(
            asin="B00OPUSTEST",
            title="Opus Audiobook",
            status=BookStatus.COMPLETED,
            local_path_converted=str(audio_file),
            conversion_format="opus",
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00OPUSTEST")

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/opus"

    @pytest.mark.asyncio
    async def test_stream_audio_book_not_found(
        self,
        client: AsyncClient,
    ) -> None:
        """Test streaming returns 404 for non-existent book."""
        response = await client.get("/stream/NONEXISTENT")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_stream_audio_book_not_completed(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test streaming returns 400 for book not in COMPLETED status."""
        audio_file = tmp_path / "not_ready.m4b"
        audio_file.write_bytes(b"fake")
        book = Book(
            asin="B00NOTREADY",
            title="Incomplete Book",
            status=BookStatus.DOWNLOADING,
            local_path_converted=str(audio_file),
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00NOTREADY")

        assert response.status_code == 400
        data = response.json()
        assert "not ready" in data["detail"].lower()
        assert "DOWNLOADING" in data["detail"]

    @pytest.mark.asyncio
    async def test_stream_audio_book_status_new(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test streaming returns 400 for NEW status book."""
        audio_file = tmp_path / "new_status.m4b"
        audio_file.write_bytes(b"fake")
        book = Book(
            asin="B00NEWBOOK",
            title="New Book",
            status=BookStatus.NEW,
            local_path_converted=str(audio_file),
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00NEWBOOK")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_stream_audio_book_status_converting(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test streaming returns 400 for CONVERTING status book."""
        audio_file = tmp_path / "converting_status.m4b"
        audio_file.write_bytes(b"fake")
        book = Book(
            asin="B00CONVERTING",
            title="Converting Book",
            status=BookStatus.CONVERTING,
            local_path_converted=str(audio_file),
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00CONVERTING")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_stream_audio_book_status_failed(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test streaming returns 400 for FAILED status book."""
        audio_file = tmp_path / "failed_status.m4b"
        audio_file.write_bytes(b"fake")
        book = Book(
            asin="B00FAILED",
            title="Failed Book",
            status=BookStatus.FAILED,
            error_message="Conversion failed",
            local_path_converted=str(audio_file),
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00FAILED")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_stream_audio_no_converted_path(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test streaming returns 404 when converted file path is not set."""
        book = Book(
            asin="B00NOPATH",
            title="No Path Book",
            status=BookStatus.COMPLETED,
            local_path_converted=None,
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00NOPATH")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_stream_audio_file_not_on_disk(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test streaming returns 404 when file doesn't exist on disk."""
        book = Book(
            asin="B00NOFILE",
            title="Missing File Book",
            status=BookStatus.COMPLETED,
            local_path_converted="/nonexistent/path/audio.m4b",
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00NOFILE")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_stream_includes_cache_control(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test streaming response includes cache control headers."""
        audio_file = tmp_path / "test_audio.m4b"
        audio_file.write_bytes(b"fake audio content")

        book = Book(
            asin="B00CACHE",
            title="Cache Test Book",
            status=BookStatus.COMPLETED,
            local_path_converted=str(audio_file),
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00CACHE")

        assert response.status_code == 200
        assert "cache-control" in response.headers


class TestStreamInfoEndpoint:
    """Tests for GET /stream/{asin}/info endpoint."""

    @pytest.mark.asyncio
    async def test_get_stream_info_available(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test getting stream info for available book."""
        audio_file = tmp_path / "test_audio.m4b"
        audio_file.write_bytes(b"fake audio content for testing")

        book = Book(
            asin="B00INFO01",
            title="Stream Info Test",
            status=BookStatus.COMPLETED,
            local_path_converted=str(audio_file),
            conversion_format="m4b",
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00INFO01/info")

        assert response.status_code == 200
        data = response.json()

        assert data["available"] is True
        assert data["asin"] == "B00INFO01"
        assert data["title"] == "Stream Info Test"
        assert data["status"] == "COMPLETED"
        assert data["format"] == "m4b"
        assert data["file_size"] is not None
        assert data["file_size"] > 0
        assert data["media_type"] == "audio/mp4"

    @pytest.mark.asyncio
    async def test_get_stream_info_not_available(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test getting stream info for book not yet converted."""
        book = Book(
            asin="B00INFO02",
            title="Not Ready Book",
            status=BookStatus.DOWNLOADING,
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00INFO02/info")

        assert response.status_code == 200
        data = response.json()

        assert data["available"] is False
        assert data["asin"] == "B00INFO02"
        assert data["status"] == "DOWNLOADING"

    @pytest.mark.asyncio
    async def test_get_stream_info_book_not_found(
        self,
        client: AsyncClient,
    ) -> None:
        """Test getting stream info for non-existent book."""
        response = await client.get("/stream/NONEXISTENT/info")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_stream_info_file_missing(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test getting stream info when file is missing from disk."""
        book = Book(
            asin="B00INFOMISSING",
            title="Missing File",
            status=BookStatus.COMPLETED,
            local_path_converted="/nonexistent/path.m4b",
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00INFOMISSING/info")

        assert response.status_code == 200
        data = response.json()

        assert data["available"] is False

    @pytest.mark.asyncio
    async def test_get_stream_info_no_path_set(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test getting stream info when no path is set."""
        book = Book(
            asin="B00INFONOPATH",
            title="No Path Set",
            status=BookStatus.NEW,
            local_path_converted=None,
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00INFONOPATH/info")

        assert response.status_code == 200
        data = response.json()

        assert data["available"] is False
        assert data["status"] == "NEW"


class TestJITStreamingEndpoints:
    """Tests for JIT streaming functionality."""

    @pytest.mark.asyncio
    async def test_stream_prefers_converted_file(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test that converted file is preferred over JIT streaming."""
        # Create both converted and source files
        converted_file = tmp_path / "converted.m4b"
        converted_file.write_bytes(b"converted audio content")

        source_file = tmp_path / "source.aaxc"
        source_file.write_bytes(b"source audio content")

        voucher_file = tmp_path / "source.voucher"
        voucher_data = {
            "content_license": {
                "license_response": {"key": "testkey", "iv": "testiv"}
            }
        }
        voucher_file.write_text(json.dumps(voucher_data))

        book = Book(
            asin="B00PREFER_CONVERTED",
            title="Prefer Converted Test",
            status=BookStatus.COMPLETED,
            local_path_converted=str(converted_file),
            local_path_aax=str(source_file),
            local_path_voucher=str(voucher_file),
            conversion_format="m4b",
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00PREFER_CONVERTED")

        assert response.status_code == 200
        # FileResponse for converted files includes Accept-Ranges
        assert response.headers.get("accept-ranges") == "bytes"
        # JIT streams have X-Stream-Mode header
        assert response.headers.get("x-stream-mode") is None

    @pytest.mark.asyncio
    async def test_stream_info_shows_jit_available(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test stream info shows JIT availability."""
        source_file = tmp_path / "source.aaxc"
        source_file.write_bytes(b"source audio content")

        voucher_file = tmp_path / "source.voucher"
        voucher_data = {
            "content_license": {
                "license_response": {"key": "testkey", "iv": "testiv"}
            }
        }
        voucher_file.write_text(json.dumps(voucher_data))

        book = Book(
            asin="B00JIT_INFO",
            title="JIT Info Test",
            status=BookStatus.DOWNLOADED,
            local_path_aax=str(source_file),
            local_path_voucher=str(voucher_file),
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00JIT_INFO/info")

        assert response.status_code == 200
        data = response.json()

        assert data["jit_available"] is True
        assert data["stream_mode"] == "jit"
        assert data["available"] is True
        assert "jit_format" in data
        assert "jit_bitrate" in data
        assert "jit_media_type" in data

    @pytest.mark.asyncio
    async def test_stream_info_jit_not_available_without_voucher(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test JIT is not available for AAXC without voucher."""
        source_file = tmp_path / "source.aaxc"
        source_file.write_bytes(b"source audio content")

        book = Book(
            asin="B00NO_VOUCHER",
            title="No Voucher Test",
            status=BookStatus.DOWNLOADED,
            local_path_aax=str(source_file),
            local_path_voucher=None,
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00NO_VOUCHER/info")

        assert response.status_code == 200
        data = response.json()

        assert data["jit_available"] is False
        assert data["stream_mode"] is None
        assert data["available"] is False

    @pytest.mark.asyncio
    async def test_stream_info_jit_available_for_aax(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test JIT is available for AAX files without voucher."""
        source_file = tmp_path / "source.aax"
        source_file.write_bytes(b"source audio content")

        book = Book(
            asin="B00AAX_JIT",
            title="AAX JIT Test",
            status=BookStatus.DOWNLOADED,
            local_path_aax=str(source_file),
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00AAX_JIT/info")

        assert response.status_code == 200
        data = response.json()

        assert data["jit_available"] is True
        assert data["stream_mode"] == "jit"

    @pytest.mark.asyncio
    async def test_stream_404_no_audio_source(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test 404 when no audio source available."""
        book = Book(
            asin="B00NO_SOURCE",
            title="No Source Test",
            status=BookStatus.NEW,
            local_path_aax=None,
            local_path_converted=None,
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00NO_SOURCE")

        assert response.status_code == 404
        data = response.json()
        assert "No audio source available" in data["detail"]

    @pytest.mark.asyncio
    async def test_jit_status_endpoint(
        self,
        client: AsyncClient,
    ) -> None:
        """Test JIT status endpoint returns service info."""
        response = await client.get("/stream/jit/status")

        assert response.status_code == 200
        data = response.json()

        assert "active_streams" in data
        assert "stream_count" in data
        assert "max_concurrent" in data
        assert "default_format" in data
        assert "default_bitrate" in data
        assert isinstance(data["active_streams"], list)
        assert isinstance(data["stream_count"], int)

    @pytest.mark.asyncio
    async def test_stream_info_with_both_sources(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test stream info when both converted and source are available."""
        converted_file = tmp_path / "converted.m4b"
        converted_file.write_bytes(b"converted audio content")

        source_file = tmp_path / "source.aaxc"
        source_file.write_bytes(b"source audio content")

        voucher_file = tmp_path / "source.voucher"
        voucher_data = {
            "content_license": {
                "license_response": {"key": "testkey", "iv": "testiv"}
            }
        }
        voucher_file.write_text(json.dumps(voucher_data))

        book = Book(
            asin="B00BOTH_SOURCES",
            title="Both Sources Test",
            status=BookStatus.COMPLETED,
            local_path_converted=str(converted_file),
            local_path_aax=str(source_file),
            local_path_voucher=str(voucher_file),
            conversion_format="m4b",
        )
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/stream/B00BOTH_SOURCES/info")

        assert response.status_code == 200
        data = response.json()

        # Both should be available
        assert data["available"] is True
        assert data["jit_available"] is True
        # But stream mode should prefer file
        assert data["stream_mode"] == "file"
        # Should have file info
        assert data["format"] == "m4b"
        assert data["file_size"] is not None
        # Should also have JIT info
        assert "jit_format" in data

    @pytest.mark.asyncio
    async def test_cancel_jit_stream_not_found(
        self,
        client: AsyncClient,
    ) -> None:
        """Test cancelling a non-existent JIT stream."""
        response = await client.delete("/stream/jit/NONEXISTENT")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is False
        assert "No active JIT stream" in data["message"]
        assert data["asin"] == "NONEXISTENT"
