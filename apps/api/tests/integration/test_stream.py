"""Integration tests for audio streaming endpoints."""

import tempfile
from pathlib import Path
from typing import Any

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
    ) -> None:
        """Test streaming returns 400 for book not in COMPLETED status."""
        book = Book(
            asin="B00NOTREADY",
            title="Incomplete Book",
            status=BookStatus.DOWNLOADING,
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
    ) -> None:
        """Test streaming returns 400 for NEW status book."""
        book = Book(
            asin="B00NEWBOOK",
            title="New Book",
            status=BookStatus.NEW,
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
    ) -> None:
        """Test streaming returns 400 for CONVERTING status book."""
        book = Book(
            asin="B00CONVERTING",
            title="Converting Book",
            status=BookStatus.CONVERTING,
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
    ) -> None:
        """Test streaming returns 400 for FAILED status book."""
        book = Book(
            asin="B00FAILED",
            title="Failed Book",
            status=BookStatus.FAILED,
            error_message="Conversion failed",
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
