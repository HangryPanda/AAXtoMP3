"""Integration tests for JIT streaming execution."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Book, BookStatus
from services.jit_streaming import JITStreamingError


@pytest.fixture
def mock_subprocess():
    """Mock asyncio subprocess."""
    process_mock = MagicMock()
    process_mock.returncode = 0
    process_mock.stdout.read = AsyncMock(side_effect=[b"chunk1", b"chunk2", b""])
    process_mock.wait = AsyncMock(return_value=None)
    process_mock.terminate = MagicMock()
    process_mock.kill = MagicMock()
    return process_mock


class TestJITExecution:
    """Tests for actual JIT streaming execution using mocks."""

    @pytest.mark.asyncio
    async def test_jit_stream_aax_success(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
        mock_subprocess: MagicMock,
    ) -> None:
        """Test successful JIT streaming of AAX file."""
        # Setup source file
        source_file = tmp_path / "book.aax"
        source_file.write_bytes(b"dummy aax content")

        # Create book
        book = Book(
            asin="B00JIT_AAX",
            title="JIT AAX Test",
            status=BookStatus.DOWNLOADED,
            local_path_aax=str(source_file),
        )
        test_session.add(book)
        await test_session.commit()

        # Mock AudibleClient and subprocess
        with patch("services.jit_streaming.AudibleClient") as MockClient:
            mock_client_instance = MockClient.return_value
            mock_client_instance.get_activation_bytes = AsyncMock(return_value="deadbeef")
            
            with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_subprocess

                response = await client.get("/stream/B00JIT_AAX")

                assert response.status_code == 200
                assert response.headers["x-stream-mode"] == "jit"
                # Check headers for default mp3 format
                assert response.headers["content-type"] == "audio/mpeg"
                
                # Verify content
                content = b""
                async for chunk in response.aiter_bytes():
                    content += chunk
                assert content == b"chunk1chunk2"

                # Verify ffmpeg command
                mock_exec.assert_called_once()
                args = mock_exec.call_args[0]
                cmd = list(args)
                
                # Check key parts of command
                assert "ffmpeg" in cmd
                assert "-activation_bytes" in cmd
                assert "deadbeef" in cmd
                assert "-i" in cmd
                assert str(source_file) in cmd
                assert "pipe:1" in cmd

    @pytest.mark.asyncio
    async def test_jit_stream_aaxc_success(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
        mock_subprocess: MagicMock,
    ) -> None:
        """Test successful JIT streaming of AAXC file with voucher."""
        # Setup files
        source_file = tmp_path / "book.aaxc"
        source_file.write_bytes(b"dummy aaxc content")
        
        voucher_file = tmp_path / "book.voucher"
        voucher_data = {
            "content_license": {
                "license_response": {"key": "secret_key", "iv": "secret_iv"}
            }
        }
        voucher_file.write_text(json.dumps(voucher_data))

        # Create book
        book = Book(
            asin="B00JIT_AAXC",
            title="JIT AAXC Test",
            status=BookStatus.DOWNLOADED,
            local_path_aax=str(source_file),
            local_path_voucher=str(voucher_file),
        )
        test_session.add(book)
        await test_session.commit()

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_subprocess

            response = await client.get("/stream/B00JIT_AAXC")

            assert response.status_code == 200
            assert response.headers["x-stream-mode"] == "jit"
            
            # Verify ffmpeg command used voucher keys
            mock_exec.assert_called_once()
            args = mock_exec.call_args[0]
            cmd = list(args)
            
            assert "-audible_key" in cmd
            assert "secret_key" in cmd
            assert "-audible_iv" in cmd
            assert "secret_iv" in cmd

    @pytest.mark.asyncio
    async def test_jit_stream_seek(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
        mock_subprocess: MagicMock,
    ) -> None:
        """Test JIT streaming with start_time parameter."""
        source_file = tmp_path / "book.aax"
        source_file.write_bytes(b"dummy aax content")

        book = Book(
            asin="B00JIT_SEEK",
            title="JIT Seek Test",
            status=BookStatus.DOWNLOADED,
            local_path_aax=str(source_file),
        )
        test_session.add(book)
        await test_session.commit()

        with patch("services.jit_streaming.AudibleClient") as MockClient:
            MockClient.return_value.get_activation_bytes = AsyncMock(return_value="deadbeef")
            
            with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_subprocess

                # Request with start_time
                response = await client.get("/stream/B00JIT_SEEK?start_time=120.5")

                assert response.status_code == 200
                
                # Verify command has seek parameter BEFORE input
                mock_exec.assert_called_once()
                args = mock_exec.call_args[0]
                cmd = list(args)
                
                assert "-ss" in cmd
                assert "120.5" in cmd
                
                ss_idx = cmd.index("-ss")
                i_idx = cmd.index("-i")
                assert ss_idx < i_idx, "Seek parameter must come before input file"

    @pytest.mark.asyncio
    async def test_jit_stream_ffmpeg_failure(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Test handling of ffmpeg startup failure."""
        source_file = tmp_path / "book.aax"
        source_file.write_bytes(b"dummy aax content")

        book = Book(
            asin="B00JIT_FAIL",
            title="JIT Fail Test",
            status=BookStatus.DOWNLOADED,
            local_path_aax=str(source_file),
        )
        test_session.add(book)
        await test_session.commit()

        with patch("services.jit_streaming.AudibleClient") as MockClient:
            MockClient.return_value.get_activation_bytes = AsyncMock(return_value="deadbeef")
            
            with patch("asyncio.create_subprocess_exec", side_effect=OSError("Exec format error")):
                # The exception occurs during streaming, so the client raises it
                # Service wraps OSError in JITStreamingError
                with pytest.raises(JITStreamingError, match="Failed to launch FFmpeg"):
                    await client.get("/stream/B00JIT_FAIL")
